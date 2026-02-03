import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { PrismaService } from '../database/prisma.service';

export interface JobConfig {
  id: string;
  name: string;
  jenkinsPath: string;
  displayName: string;
  type: 'docker' | 'server';
  description?: string;
  parameters: string[];
  tags: {
    display: string[];
    filters: string[];
  };
}

interface JobsConfig {
  jobs: JobConfig[];
}

@Injectable()
export class JobsService implements OnModuleInit {
  private readonly logger = new Logger(JobsService.name);
  private jobs: JobConfig[] = [];
  private readonly jenkinsUrl: string;

  constructor(
    private configService: ConfigService,
    private prisma: PrismaService,
  ) {
    this.jenkinsUrl = this.configService.get<string>('JENKINS_URL');
  }

  async onModuleInit() {
    await this.loadJobsConfig();
    await this.seedJobs();
  }

  private async loadJobsConfig() {
    try {
      const configPath = path.join(process.cwd(), 'config', 'jobs.yaml');
      const fileContents = fs.readFileSync(configPath, 'utf8');
      const config = yaml.load(fileContents) as JobsConfig;
      this.jobs = config.jobs;
      this.logger.log(`Loaded ${this.jobs.length} job configurations`);
    } catch (error) {
      this.logger.error(`Failed to load jobs config: ${error.message}`);
      this.jobs = [];
    }
  }

  private async seedJobs() {
    try {
      for (const jobConfig of this.jobs) {
        await this.prisma.job.upsert({
          where: { id: jobConfig.id },
          update: {
            name: jobConfig.name,
            jenkinsPath: jobConfig.jenkinsPath,
            displayName: jobConfig.displayName,
            type: jobConfig.type,
          },
          create: {
            id: jobConfig.id,
            name: jobConfig.name,
            jenkinsPath: jobConfig.jenkinsPath,
            displayName: jobConfig.displayName,
            type: jobConfig.type,
          },
        });
      }
      this.logger.log('Job configurations seeded to database');
    } catch (error) {
      this.logger.error(`Failed to seed jobs: ${error.message}`);
    }
  }

  getAllJobs(): JobConfig[] {
    return this.jobs;
  }

  getJob(jobId: string): JobConfig | undefined {
    return this.jobs.find(job => job.id === jobId);
  }

  getJobJenkinsUrl(jobId: string): string {
    const job = this.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }
    return `${this.jenkinsUrl}/${job.jenkinsPath}`;
  }
}
