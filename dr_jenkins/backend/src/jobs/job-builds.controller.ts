import { Controller, Get, Param, Query, Post, NotFoundException } from '@nestjs/common';
import { JobBuildsService } from './job-builds.service';
import { JobsService } from './jobs.service';

@Controller('api/jobs/:jobId')
export class JobBuildsController {
  constructor(
    private readonly jobBuildsService: JobBuildsService,
    private readonly jobsService: JobsService,
  ) {}

  @Get('builds')
  async getBuilds(
    @Param('jobId') jobId: string,
    @Query() query: any,
  ) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    const params = {
      ...query,
      page: query.page ? parseInt(query.page, 10) : undefined,
      limit: query.limit ? parseInt(query.limit, 10) : undefined,
    };

    return this.jobBuildsService.getBuilds(jobId, params);
  }

  @Get('builds/:buildId')
  async getBuild(
    @Param('jobId') jobId: string,
    @Param('buildId') buildId: string,
  ) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    return this.jobBuildsService.getBuildById(jobId, parseInt(buildId, 10));
  }

  @Get('builds/:buildId/logs')
  async getBuildLogs(
    @Param('jobId') jobId: string,
    @Param('buildId') buildId: string,
  ) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    const logs = await this.jobBuildsService.getBuildLogs(jobId, parseInt(buildId, 10));
    return { buildId: parseInt(buildId, 10), logs };
  }

  @Get('status')
  async getStatus(@Param('jobId') jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    return this.jobBuildsService.getJobStatus(jobId);
  }

  @Get('stats')
  async getStats(@Param('jobId') jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    return this.jobBuildsService.getBuildStats(jobId);
  }

  @Get('stats/overall')
  async getOverallStats(@Param('jobId') jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    return this.jobBuildsService.getOverallStats(jobId);
  }

  @Get('stats/branch-types')
  async getBranchTypeStats(@Param('jobId') jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    return this.jobBuildsService.getBranchTypeStats(jobId);
  }

  @Get('stats/daily')
  async getDailyStats(
    @Param('jobId') jobId: string,
    @Query('days') days?: string,
  ) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    const daysNumber = days ? parseInt(days, 10) : 30;
    return this.jobBuildsService.getDailyStats(jobId, daysNumber);
  }

  @Get('stats/duration-trend')
  async getDurationTrend(
    @Param('jobId') jobId: string,
    @Query('limit') limit?: string,
  ) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    const limitNumber = limit ? parseInt(limit, 10) : 100;
    return this.jobBuildsService.getDurationTrend(jobId, limitNumber);
  }

  @Post('scrape/initial')
  async scrapeInitial(@Param('jobId') jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    await this.jobBuildsService.scrapeInitialHistory(jobId);
    return { message: 'Initial history scraping started' };
  }

  @Post('scrape/recent')
  async scrapeRecent(@Param('jobId') jobId: string) {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new NotFoundException(`Job ${jobId} not found`);
    }

    await this.jobBuildsService.scrapeRecentBuilds(jobId);
    return { message: 'Recent builds scraped successfully' };
  }
}
