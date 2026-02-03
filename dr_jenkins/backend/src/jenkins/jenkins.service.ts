import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';
import { PrismaService } from '../database/prisma.service';

interface BuildInfo {
  id: number;
  status: string;
  duration: number | null;
  timestamp: Date;
  url: string;
  parameters: { name: string; value: string }[];
  logs?: string;
  userName?: string;
  imageTag?: string;
}

@Injectable()
export class JenkinsService {
  private readonly logger = new Logger(JenkinsService.name);
  private readonly jenkinsUrl: string;
  private readonly apiToken: string;
  private readonly jobPath: string;
  private readonly baseJobUrl: string;

  constructor(
    private configService: ConfigService,
    private prisma: PrismaService,
  ) {
    this.jenkinsUrl = this.configService.get<string>('JENKINS_URL');
    this.apiToken = this.configService.get<string>('JENKINS_API_TOKEN');
    this.jobPath = this.configService.get<string>('JENKINS_JOB_PATH');
    this.baseJobUrl = `${this.jenkinsUrl}/${this.jobPath}`;
  }

  private getAuthHeaders() {
    // Jenkins API Token 사용 시 username:token 형식으로 Basic Auth
    // 또는 인증 없이 시도 (Jenkins가 익명 접근 허용하는 경우)
    if (this.apiToken) {
      // API Token이 username:token 형식인 경우
      const auth = Buffer.from(this.apiToken).toString('base64');
      return {
        Authorization: `Basic ${auth}`,
      };
    }
    return {};
  }

  async getLatestBuildId(): Promise<number> {
    try {
      const url = `${this.baseJobUrl}/api/json`;
      const response = await axios.get(url, {
        headers: this.getAuthHeaders(),
      });
      return response.data.lastBuild?.number || 0;
    } catch (error) {
      this.logger.error(`Failed to get latest build ID: ${error.message}`);
      return 0;
    }
  }

  async scrapeBuildInfo(buildId: number): Promise<BuildInfo | null> {
    try {
      const buildUrl = `${this.baseJobUrl}/${buildId}`;

      // Use Jenkins API JSON directly - much faster!
      const apiUrl = `${this.baseJobUrl}/${buildId}/api/json`;
      const apiResponse = await axios.get(apiUrl, {
        headers: this.getAuthHeaders(),
        timeout: 10000,
      });

      const { duration, timestamp, result, actions } = apiResponse.data;

      // Extract parameters, user info, and image tag from actions
      const parameters: { name: string; value: string }[] = [];
      let userName: string | undefined;
      let imageTag: string | undefined;

      if (actions && Array.isArray(actions)) {
        for (const action of actions) {
          // Extract parameters
          if (action._class === 'hudson.model.ParametersAction' && action.parameters) {
            for (const param of action.parameters) {
              if (param.name && param.value !== undefined) {
                parameters.push({
                  name: param.name,
                  value: String(param.value),
                });
              }
            }
          }

          // Extract user who started the build
          if (action._class === 'hudson.model.CauseAction' && action.causes) {
            for (const cause of action.causes) {
              if (cause.userName) {
                userName = cause.userName;
                break;
              } else if (cause.userId) {
                userName = cause.userId;
                break;
              }
            }
          }
        }
      }

      // Calculate image tag from parameters if not found
      imageTag = this.calculateImageTag(buildId, parameters);

      const buildInfo: BuildInfo = {
        id: buildId,
        status: result || 'IN_PROGRESS',
        duration: duration || null,
        timestamp: new Date(timestamp),
        url: buildUrl,
        parameters,
        userName,
        imageTag,
      };

      return buildInfo;
    } catch (error) {
      this.logger.error(`Failed to scrape build ${buildId}: ${error.message}`);
      return null;
    }
  }

  // Removed - parameters are now extracted directly from build API JSON

  private calculateImageTag(buildId: number, parameters: { name: string; value: string }[]): string {
    // TAG format: {BASE_VERSION}.{BUILD_NUMBER}{-arm if ARM64}
    const baseVersion = parameters.find(p => p.name === 'BASE_VERSION')?.value || '0.1';
    const target = parameters.find(p => p.name === 'TARGET')?.value;
    const suffix = target === 'ARM64' ? '-arm' : '';
    return `${baseVersion}.${buildId}${suffix}`;
  }

  async getBuildLogs(buildId: number): Promise<string> {
    try {
      const logsUrl = `${this.baseJobUrl}/${buildId}/consoleText`;
      const response = await axios.get(logsUrl, {
        headers: this.getAuthHeaders(),
        timeout: 30000,
      });
      return response.data;
    } catch (error) {
      this.logger.error(`Failed to get logs for build ${buildId}: ${error.message}`);
      return '';
    }
  }

  async saveBuildToDatabase(buildInfo: BuildInfo): Promise<void> {
    try {
      await this.prisma.dockerBuild.upsert({
        where: { id: buildInfo.id },
        update: {
          status: buildInfo.status,
          duration: buildInfo.duration,
          timestamp: buildInfo.timestamp,
          url: buildInfo.url,
          userName: buildInfo.userName,
          imageTag: buildInfo.imageTag,
          parameters: {
            deleteMany: {},
            create: buildInfo.parameters.map(p => ({
              name: p.name,
              value: p.value,
            })),
          },
        },
        create: {
          id: buildInfo.id,
          status: buildInfo.status,
          duration: buildInfo.duration,
          timestamp: buildInfo.timestamp,
          url: buildInfo.url,
          userName: buildInfo.userName,
          imageTag: buildInfo.imageTag,
          parameters: {
            create: buildInfo.parameters.map(p => ({
              name: p.name,
              value: p.value,
            })),
          },
        },
      });
      this.logger.log(`Saved docker build ${buildInfo.id} to database`);
    } catch (error) {
      this.logger.error(`Failed to save docker build ${buildInfo.id}: ${error.message}`);
    }
  }

  async scrapeInitialHistory(progressCallback?: (current: number, total: number) => void): Promise<void> {
    this.logger.log('Starting initial history scraping...');
    const latestBuildId = await this.getLatestBuildId();

    if (latestBuildId === 0) {
      this.logger.error('Could not determine latest build ID');
      return;
    }

    this.logger.log(`Found latest build ID: ${latestBuildId}`);

    // Scrape in batches for better performance
    const batchSize = 10;
    for (let id = 1; id <= latestBuildId; id += batchSize) {
      const endId = Math.min(id + batchSize - 1, latestBuildId);
      const promises = [];

      for (let batchId = id; batchId <= endId; batchId++) {
        promises.push(
          this.scrapeBuildInfo(batchId).then(buildInfo => {
            if (buildInfo) {
              return this.saveBuildToDatabase(buildInfo);
            }
          })
        );
      }

      // Process batch in parallel
      await Promise.all(promises);

      if (progressCallback) {
        progressCallback(endId, latestBuildId);
      }

      // Log progress every batch
      this.logger.log(`Progress: ${endId}/${latestBuildId} (${((endId / latestBuildId) * 100).toFixed(1)}%)`);

      // Small delay between batches
      await new Promise(resolve => setTimeout(resolve, 200));
    }

    this.logger.log('Initial history scraping completed');
  }

  async scrapeRecentBuilds(count: number = 100): Promise<void> {
    this.logger.log(`Scraping recent ${count} builds...`);
    const latestBuildId = await this.getLatestBuildId();

    if (latestBuildId === 0) {
      this.logger.error('Could not determine latest build ID');
      return;
    }

    const startId = Math.max(1, latestBuildId - count + 1);

    // Process in parallel batches of 20 for speed
    const batchSize = 20;
    for (let id = startId; id <= latestBuildId; id += batchSize) {
      const endId = Math.min(id + batchSize - 1, latestBuildId);
      const promises = [];

      for (let batchId = id; batchId <= endId; batchId++) {
        promises.push(
          this.scrapeBuildInfo(batchId).then(buildInfo => {
            if (buildInfo) {
              return this.saveBuildToDatabase(buildInfo);
            }
          })
        );
      }

      await Promise.all(promises);
    }

    this.logger.log(`Scraped ${latestBuildId - startId + 1} recent builds`);
  }

  async updateBuildLogs(buildId: number): Promise<void> {
    const logs = await this.getBuildLogs(buildId);
    if (logs) {
      await this.prisma.dockerBuild.update({
        where: { id: buildId },
        data: { logs },
      });
      this.logger.log(`Updated logs for docker build ${buildId}`);
    }
  }
}
