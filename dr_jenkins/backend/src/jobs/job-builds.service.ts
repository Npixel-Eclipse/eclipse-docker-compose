import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { JenkinsService } from '../jenkins/jenkins.service';
import { JobsService } from './jobs.service';
import { Prisma } from '@prisma/client';
import axios from 'axios';
import { ConfigService } from '@nestjs/config';

interface BuildsQueryParams {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
  [key: string]: any; // For dynamic filter parameters like P4STREAM, BUILD_TYPE, etc.
}

interface BuildInfo {
  id: number;
  status: string;
  duration: number | null;
  timestamp: Date;
  url: string;
  parameters: { name: string; value: string }[];
  userName?: string;
  imageTag?: string;
}

@Injectable()
export class JobBuildsService {
  private readonly logger = new Logger(JobBuildsService.name);
  private readonly jenkinsUrl: string;
  private readonly apiToken: string;

  constructor(
    private prisma: PrismaService,
    private jenkinsService: JenkinsService,
    private jobsService: JobsService,
    private configService: ConfigService,
  ) {
    this.jenkinsUrl = this.configService.get<string>('JENKINS_URL');
    this.apiToken = this.configService.get<string>('JENKINS_API_TOKEN');
  }

  private getAuthHeaders() {
    if (this.apiToken) {
      const auth = Buffer.from(this.apiToken).toString('base64');
      return { Authorization: `Basic ${auth}` };
    }
    return {};
  }

  async getBuilds(jobId: string, params: BuildsQueryParams) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    const { page = 1, limit = 50, status, search, ...filterParams } = params;
    const skip = (page - 1) * limit;

    if (job.type === 'docker') {
      return this.getDockerBuilds({ page, limit, status, search, ...filterParams }, skip);
    } else if (job.type === 'server') {
      return this.getServerBuilds({ page, limit, status, search, ...filterParams }, skip);
    }

    throw new Error(`Unknown job type: ${job.type}`);
  }

  private async getDockerBuilds(params: BuildsQueryParams, skip: number) {
    const { page = 1, limit = 50, status, search, branchType, target } = params;
    const where: Prisma.DockerBuildWhereInput = {};

    if (status) where.status = status;

    const paramConditions: any[] = [];
    if (branchType) {
      paramConditions.push({ name: 'BRANCH_TYPE', value: branchType });
    }
    if (target) {
      paramConditions.push({ name: 'TARGET', value: target });
    }

    if (paramConditions.length > 0) {
      where.parameters = { some: { OR: paramConditions } };
    }

    if (search) {
      where.OR = [
        { id: isNaN(Number(search)) ? undefined : Number(search) },
        { parameters: { some: { value: { contains: search, mode: 'insensitive' } } } },
      ];
    }

    const [builds, total] = await Promise.all([
      this.prisma.dockerBuild.findMany({
        where,
        include: { parameters: true },
        orderBy: { id: 'desc' },
        skip,
        take: limit,
      }),
      this.prisma.dockerBuild.count({ where }),
    ]);

    return {
      data: builds,
      meta: { total, page, limit, totalPages: Math.ceil(total / limit) },
    };
  }

  private async getServerBuilds(params: BuildsQueryParams, skip: number) {
    const { page = 1, limit = 50, status, search, p4Stream, buildType } = params;
    const where: Prisma.ServerBuildWhereInput = {};

    if (status) where.status = status;

    const paramConditions: any[] = [];
    if (p4Stream) {
      paramConditions.push({ name: 'P4STREAM', value: p4Stream });
    }
    if (buildType) {
      paramConditions.push({ name: 'BUILD_TYPE', value: buildType });
    }

    if (paramConditions.length > 0) {
      where.parameters = { some: { OR: paramConditions } };
    }

    if (search) {
      where.OR = [
        { id: isNaN(Number(search)) ? undefined : Number(search) },
        { parameters: { some: { value: { contains: search, mode: 'insensitive' } } } },
      ];
    }

    const [builds, total] = await Promise.all([
      this.prisma.serverBuild.findMany({
        where,
        include: { parameters: true },
        orderBy: { id: 'desc' },
        skip,
        take: limit,
      }),
      this.prisma.serverBuild.count({ where }),
    ]);

    return {
      data: builds,
      meta: { total, page, limit, totalPages: Math.ceil(total / limit) },
    };
  }

  async getBuildById(jobId: string, buildId: number) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    if (job.type === 'docker') {
      return this.prisma.dockerBuild.findUnique({
        where: { id: buildId },
        include: { parameters: true },
      });
    } else if (job.type === 'server') {
      return this.prisma.serverBuild.findUnique({
        where: { id: buildId },
        include: { parameters: true },
      });
    }

    return null;
  }

  async getBuildLogs(jobId: string, buildId: number): Promise<string> {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    let logs = '';

    if (job.type === 'docker') {
      const build = await this.prisma.dockerBuild.findUnique({
        where: { id: buildId },
        select: { logs: true },
      });
      logs = build?.logs || '';
    } else if (job.type === 'server') {
      const build = await this.prisma.serverBuild.findUnique({
        where: { id: buildId },
        select: { logs: true },
      });
      logs = build?.logs || '';
    }

    // If logs not in database, fetch from Jenkins
    if (!logs) {
      try {
        const logsUrl = `${this.jenkinsUrl}/${job.jenkinsPath}/${buildId}/consoleText`;
        const response = await axios.get(logsUrl, {
          headers: this.getAuthHeaders(),
          timeout: 30000,
        });
        logs = response.data;

        // Save logs to database for future use
        if (logs && job.type === 'docker') {
          await this.prisma.dockerBuild.update({
            where: { id: buildId },
            data: { logs },
          });
        } else if (logs && job.type === 'server') {
          await this.prisma.serverBuild.update({
            where: { id: buildId },
            data: { logs },
          });
        }
      } catch (error) {
        this.logger.error(`Failed to fetch logs for build ${buildId}: ${error.message}`);
      }
    }

    return logs;
  }

  async getBuildStats(jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    if (job.type === 'docker') {
      const [total, success, failure] = await Promise.all([
        this.prisma.dockerBuild.count(),
        this.prisma.dockerBuild.count({ where: { status: 'SUCCESS' } }),
        this.prisma.dockerBuild.count({ where: { status: 'FAILURE' } }),
      ]);

      const avgDuration = await this.prisma.dockerBuild.aggregate({
        _avg: { duration: true },
        where: { duration: { not: null } },
      });

      return {
        totalBuilds: total,
        successCount: success,
        failureCount: failure,
        successRate: total > 0 ? (success / total) * 100 : 0,
        averageDuration: avgDuration._avg.duration || 0,
      };
    } else if (job.type === 'server') {
      const [total, success, failure] = await Promise.all([
        this.prisma.serverBuild.count(),
        this.prisma.serverBuild.count({ where: { status: 'SUCCESS' } }),
        this.prisma.serverBuild.count({ where: { status: 'FAILURE' } }),
      ]);

      const avgDuration = await this.prisma.serverBuild.aggregate({
        _avg: { duration: true },
        where: { duration: { not: null } },
      });

      return {
        totalBuilds: total,
        successCount: success,
        failureCount: failure,
        successRate: total > 0 ? (success / total) * 100 : 0,
        averageDuration: avgDuration._avg.duration || 0,
      };
    }

    return null;
  }

  async scrapeInitialHistory(jobId: string): Promise<void> {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    this.logger.log(`Starting initial history scraping for ${job.name}...`);
    const latestBuildId = await this.getLatestBuildId(job.jenkinsPath);

    if (latestBuildId === 0) {
      this.logger.error('Could not determine latest build ID');
      return;
    }

    const batchSize = 10;
    for (let id = 1; id <= latestBuildId; id += batchSize) {
      const endId = Math.min(id + batchSize - 1, latestBuildId);
      const promises = [];

      for (let batchId = id; batchId <= endId; batchId++) {
        promises.push(
          this.scrapeBuildInfo(job.jenkinsPath, batchId, job.type).then(buildInfo => {
            if (buildInfo) {
              return this.saveBuildToDatabase(jobId, buildInfo);
            }
          })
        );
      }

      await Promise.all(promises);
      this.logger.log(`Progress: ${endId}/${latestBuildId}`);
      await new Promise(resolve => setTimeout(resolve, 200));
    }

    this.logger.log(`Initial history scraping completed for ${job.name}`);
  }

  async scrapeRecentBuilds(jobId: string, count: number = 100): Promise<void> {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    this.logger.log(`Scraping recent ${count} builds for ${job.name}...`);
    const latestBuildId = await this.getLatestBuildId(job.jenkinsPath);

    if (latestBuildId === 0) {
      this.logger.error('Could not determine latest build ID');
      return;
    }

    const startId = Math.max(1, latestBuildId - count + 1);
    const batchSize = 20;

    for (let id = startId; id <= latestBuildId; id += batchSize) {
      const endId = Math.min(id + batchSize - 1, latestBuildId);
      const promises = [];

      for (let batchId = id; batchId <= endId; batchId++) {
        promises.push(
          this.scrapeBuildInfo(job.jenkinsPath, batchId, job.type).then(buildInfo => {
            if (buildInfo) {
              return this.saveBuildToDatabase(jobId, buildInfo);
            }
          })
        );
      }

      await Promise.all(promises);
    }

    this.logger.log(`Scraped ${latestBuildId - startId + 1} recent builds for ${job.name}`);
  }

  private async getLatestBuildId(jenkinsPath: string): Promise<number> {
    try {
      const url = `${this.jenkinsUrl}/${jenkinsPath}/api/json`;
      const response = await axios.get(url, { headers: this.getAuthHeaders() });
      return response.data.lastBuild?.number || 0;
    } catch (error) {
      this.logger.error(`Failed to get latest build ID: ${error.message}`);
      return 0;
    }
  }

  private async scrapeBuildInfo(jenkinsPath: string, buildId: number, jobType: string): Promise<BuildInfo | null> {
    try {
      const apiUrl = `${this.jenkinsUrl}/${jenkinsPath}/${buildId}/api/json`;
      const apiResponse = await axios.get(apiUrl, {
        headers: this.getAuthHeaders(),
        timeout: 10000,
      });

      const { duration, timestamp, result, actions } = apiResponse.data;
      const parameters: { name: string; value: string }[] = [];
      let userName: string | undefined;

      if (actions && Array.isArray(actions)) {
        for (const action of actions) {
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

      const buildUrl = `${this.jenkinsUrl}/${jenkinsPath}/${buildId}`;
      const buildInfo: BuildInfo = {
        id: buildId,
        status: result || 'IN_PROGRESS',
        duration: duration || null,
        timestamp: new Date(timestamp),
        url: buildUrl,
        parameters,
        userName,
      };

      // Calculate imageTag for docker builds
      if (jobType === 'docker') {
        buildInfo.imageTag = this.calculateImageTag(buildId, parameters);
      }

      return buildInfo;
    } catch (error) {
      this.logger.error(`Failed to scrape build ${buildId}: ${error.message}`);
      return null;
    }
  }

  private calculateImageTag(buildId: number, parameters: { name: string; value: string }[]): string {
    const baseVersion = parameters.find(p => p.name === 'BASE_VERSION')?.value || '0.1';
    const target = parameters.find(p => p.name === 'TARGET')?.value;
    const suffix = target === 'ARM64' ? '-arm' : '';
    return `${baseVersion}.${buildId}${suffix}`;
  }

  private async saveBuildToDatabase(jobId: string, buildInfo: BuildInfo): Promise<void> {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    try {
      if (job.type === 'docker') {
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
      } else if (job.type === 'server') {
        await this.prisma.serverBuild.upsert({
          where: { id: buildInfo.id },
          update: {
            status: buildInfo.status,
            duration: buildInfo.duration,
            timestamp: buildInfo.timestamp,
            url: buildInfo.url,
            userName: buildInfo.userName,
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
            parameters: {
              create: buildInfo.parameters.map(p => ({
                name: p.name,
                value: p.value,
              })),
            },
          },
        });
      }
      this.logger.log(`Saved ${job.type} build ${buildInfo.id} to database`);
    } catch (error) {
      this.logger.error(`Failed to save build ${buildInfo.id}: ${error.message}`);
    }
  }

  async getOverallStats(jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    if (job.type === 'docker') {
      const [total, success, failure, aborted] = await Promise.all([
        this.prisma.dockerBuild.count(),
        this.prisma.dockerBuild.count({ where: { status: 'SUCCESS' } }),
        this.prisma.dockerBuild.count({ where: { status: 'FAILURE' } }),
        this.prisma.dockerBuild.count({ where: { status: 'ABORTED' } }),
      ]);

      const avgDuration = await this.prisma.dockerBuild.aggregate({
        _avg: { duration: true },
        where: { duration: { not: null } },
      });

      return {
        total,
        success,
        failure,
        aborted,
        successRate: total > 0 ? (success / total) * 100 : 0,
        failureRate: total > 0 ? (failure / total) * 100 : 0,
        averageDuration: avgDuration._avg.duration || 0,
      };
    } else if (job.type === 'server') {
      const [total, success, failure, aborted] = await Promise.all([
        this.prisma.serverBuild.count(),
        this.prisma.serverBuild.count({ where: { status: 'SUCCESS' } }),
        this.prisma.serverBuild.count({ where: { status: 'FAILURE' } }),
        this.prisma.serverBuild.count({ where: { status: 'ABORTED' } }),
      ]);

      const avgDuration = await this.prisma.serverBuild.aggregate({
        _avg: { duration: true },
        where: { duration: { not: null } },
      });

      return {
        total,
        success,
        failure,
        aborted,
        successRate: total > 0 ? (success / total) * 100 : 0,
        failureRate: total > 0 ? (failure / total) * 100 : 0,
        averageDuration: avgDuration._avg.duration || 0,
      };
    }

    return null;
  }

  async getBranchTypeStats(jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    if (job.type === 'docker') {
      // Get all unique BRANCH_TYPE values from database
      const branchTypeRecords = await this.prisma.dockerBuildParameter.findMany({
        where: {
          name: 'BRANCH_TYPE',
        },
        distinct: ['value'],
        select: { value: true },
      });

      const branchTypes = branchTypeRecords.map(r => r.value).sort();
      const stats = [];

      for (const branchType of branchTypes) {
        const buildIds = await this.prisma.dockerBuildParameter.findMany({
          where: {
            name: 'BRANCH_TYPE',
            value: branchType,
          },
          select: { dockerBuildId: true },
        });

        const buildIdList = buildIds.map(b => b.dockerBuildId);

        if (buildIdList.length === 0) {
          stats.push({
            branchType,
            total: 0,
            success: 0,
            failure: 0,
            successRate: 0,
          });
          continue;
        }

        const [total, success, failure] = await Promise.all([
          this.prisma.dockerBuild.count({
            where: { id: { in: buildIdList } },
          }),
          this.prisma.dockerBuild.count({
            where: { id: { in: buildIdList }, status: 'SUCCESS' },
          }),
          this.prisma.dockerBuild.count({
            where: { id: { in: buildIdList }, status: 'FAILURE' },
          }),
        ]);

        stats.push({
          branchType,
          total,
          success,
          failure,
          successRate: total > 0 ? (success / total) * 100 : 0,
        });
      }

      return stats;
    } else if (job.type === 'server') {
      // Get all unique BUILD_TYPE values (not P4STREAM) for consistency with Status dashboard
      const buildTypeRecords = await this.prisma.serverBuildParameter.findMany({
        where: {
          name: 'BUILD_TYPE',
        },
        distinct: ['value'],
        select: { value: true },
      });

      const buildTypes = buildTypeRecords.map(r => r.value).sort();
      const stats = [];

      for (const buildType of buildTypes) {
        const buildIds = await this.prisma.serverBuildParameter.findMany({
          where: {
            name: 'BUILD_TYPE',
            value: buildType,
          },
          select: { serverBuildId: true },
        });

        const buildIdList = buildIds.map(b => b.serverBuildId);

        if (buildIdList.length === 0) {
          stats.push({
            branchType: buildType,
            total: 0,
            success: 0,
            failure: 0,
            successRate: 0,
          });
          continue;
        }

        const [total, success, failure] = await Promise.all([
          this.prisma.serverBuild.count({
            where: { id: { in: buildIdList } },
          }),
          this.prisma.serverBuild.count({
            where: { id: { in: buildIdList }, status: 'SUCCESS' },
          }),
          this.prisma.serverBuild.count({
            where: { id: { in: buildIdList }, status: 'FAILURE' },
          }),
        ]);

        stats.push({
          branchType: buildType,
          total,
          success,
          failure,
          successRate: total > 0 ? (success / total) * 100 : 0,
        });
      }

      return stats;
    }

    return [];
  }

  async getDailyStats(jobId: string, days: number = 30) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    let builds;
    if (job.type === 'docker') {
      builds = await this.prisma.dockerBuild.findMany({
        where: {
          timestamp: {
            gte: startDate,
          },
        },
        select: {
          timestamp: true,
          status: true,
          duration: true,
        },
        orderBy: {
          timestamp: 'asc',
        },
      });
    } else if (job.type === 'server') {
      builds = await this.prisma.serverBuild.findMany({
        where: {
          timestamp: {
            gte: startDate,
          },
        },
        select: {
          timestamp: true,
          status: true,
          duration: true,
        },
        orderBy: {
          timestamp: 'asc',
        },
      });
    } else {
      return [];
    }

    // Group by date
    const dailyMap = new Map<string, { total: number; success: number; failure: number }>();

    builds.forEach(build => {
      const dateKey = build.timestamp.toISOString().split('T')[0];
      if (!dailyMap.has(dateKey)) {
        dailyMap.set(dateKey, { total: 0, success: 0, failure: 0 });
      }

      const stats = dailyMap.get(dateKey);
      stats.total++;
      if (build.status === 'SUCCESS') stats.success++;
      if (build.status === 'FAILURE') stats.failure++;
    });

    const dailyStats = Array.from(dailyMap.entries()).map(([date, stats]) => ({
      date,
      total: stats.total,
      success: stats.success,
      failure: stats.failure,
    }));

    return dailyStats;
  }

  async getDurationTrend(jobId: string, limit: number = 100) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    let builds;
    if (job.type === 'docker') {
      builds = await this.prisma.dockerBuild.findMany({
        where: {
          duration: { not: null },
        },
        select: {
          id: true,
          timestamp: true,
          duration: true,
          status: true,
        },
        orderBy: {
          id: 'desc',
        },
        take: limit,
      });
    } else if (job.type === 'server') {
      builds = await this.prisma.serverBuild.findMany({
        where: {
          duration: { not: null },
        },
        select: {
          id: true,
          timestamp: true,
          duration: true,
          status: true,
        },
        orderBy: {
          id: 'desc',
        },
        take: limit,
      });
    } else {
      return [];
    }

    return builds.reverse();
  }

  async getJobStatus(jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }

    if (job.type === 'docker') {
      // Get all unique BRANCH_TYPE values from database
      const branchTypeRecords = await this.prisma.dockerBuildParameter.findMany({
        where: {
          name: 'BRANCH_TYPE',
        },
        distinct: ['value'],
        select: { value: true },
      });

      const branchTypes = branchTypeRecords.map(r => r.value).sort();
      const statuses = [];

      for (const branchType of branchTypes) {
        // Get latest build for this branch type
        const buildIds = await this.prisma.dockerBuildParameter.findMany({
          where: {
            name: 'BRANCH_TYPE',
            value: branchType,
          },
          select: { dockerBuildId: true },
          orderBy: { dockerBuildId: 'desc' },
          take: 100, // Get recent builds to find latest and track unstable
        });

        const buildIdList = buildIds.map(b => b.dockerBuildId);

        if (buildIdList.length === 0) {
          statuses.push({
            type: branchType,
            latestBuild: null,
          });
          continue;
        }

        const latestBuild = await this.prisma.dockerBuild.findFirst({
          where: { id: { in: buildIdList } },
          orderBy: { id: 'desc' },
          include: {
            parameters: true,
          },
        });

        if (!latestBuild) {
          statuses.push({
            type: branchType,
            latestBuild: null,
          });
          continue;
        }

        let brokenBy: string | undefined;

        // If current build is UNSTABLE or FAILURE, find who broke it
        if (latestBuild.status === 'UNSTABLE' || latestBuild.status === 'FAILURE') {
          const builds = await this.prisma.dockerBuild.findMany({
            where: { id: { in: buildIdList } },
            orderBy: { id: 'desc' },
            select: {
              id: true,
              status: true,
              userName: true,
            },
          });

          // Find last SUCCESS build
          const lastSuccessIndex = builds.findIndex(b => b.status === 'SUCCESS');

          if (lastSuccessIndex > 0) {
            // Find first UNSTABLE/FAILURE after last SUCCESS
            for (let i = lastSuccessIndex - 1; i >= 0; i--) {
              if (builds[i].status === 'UNSTABLE' || builds[i].status === 'FAILURE') {
                brokenBy = builds[i].userName || 'Unknown';
                break;
              }
            }
          } else if (lastSuccessIndex === -1) {
            // No SUCCESS found, use first non-success build
            const firstFailure = builds.find(b => b.status !== 'SUCCESS');
            if (firstFailure) {
              brokenBy = firstFailure.userName || 'Unknown';
            }
          }
        }

        statuses.push({
          type: branchType,
          latestBuild: {
            id: latestBuild.id,
            status: latestBuild.status,
            userName: latestBuild.userName,
            timestamp: latestBuild.timestamp,
            duration: latestBuild.duration,
            url: latestBuild.url,
            brokenBy,
          },
        });
      }

      return statuses;
    } else if (job.type === 'server') {
      // Get all unique BUILD_TYPE values from database
      const buildTypeRecords = await this.prisma.serverBuildParameter.findMany({
        where: {
          name: 'BUILD_TYPE',
        },
        distinct: ['value'],
        select: { value: true },
      });

      const buildTypes = buildTypeRecords.map(r => r.value).sort();
      const statuses = [];

      for (const buildType of buildTypes) {
        // Get latest build for this build type
        const buildIds = await this.prisma.serverBuildParameter.findMany({
          where: {
            name: 'BUILD_TYPE',
            value: buildType,
          },
          select: { serverBuildId: true },
          orderBy: { serverBuildId: 'desc' },
          take: 100,
        });

        const buildIdList = buildIds.map(b => b.serverBuildId);

        if (buildIdList.length === 0) {
          statuses.push({
            type: buildType,
            latestBuild: null,
          });
          continue;
        }

        const latestBuild = await this.prisma.serverBuild.findFirst({
          where: { id: { in: buildIdList } },
          orderBy: { id: 'desc' },
          include: {
            parameters: true,
          },
        });

        if (!latestBuild) {
          statuses.push({
            type: buildType,
            latestBuild: null,
          });
          continue;
        }

        let brokenBy: string | undefined;

        // If current build is UNSTABLE or FAILURE, find who broke it
        if (latestBuild.status === 'UNSTABLE' || latestBuild.status === 'FAILURE') {
          const builds = await this.prisma.serverBuild.findMany({
            where: { id: { in: buildIdList } },
            orderBy: { id: 'desc' },
            select: {
              id: true,
              status: true,
              userName: true,
            },
          });

          // Find last SUCCESS build
          const lastSuccessIndex = builds.findIndex(b => b.status === 'SUCCESS');

          if (lastSuccessIndex > 0) {
            // Find first UNSTABLE/FAILURE after last SUCCESS
            for (let i = lastSuccessIndex - 1; i >= 0; i--) {
              if (builds[i].status === 'UNSTABLE' || builds[i].status === 'FAILURE') {
                brokenBy = builds[i].userName || 'Unknown';
                break;
              }
            }
          } else if (lastSuccessIndex === -1) {
            // No SUCCESS found, use first non-success build
            const firstFailure = builds.find(b => b.status !== 'SUCCESS');
            if (firstFailure) {
              brokenBy = firstFailure.userName || 'Unknown';
            }
          }
        }

        statuses.push({
          type: buildType,
          latestBuild: {
            id: latestBuild.id,
            status: latestBuild.status,
            userName: latestBuild.userName,
            timestamp: latestBuild.timestamp,
            duration: latestBuild.duration,
            url: latestBuild.url,
            brokenBy,
          },
        });
      }

      return statuses;
    }

    return [];
  }
}
