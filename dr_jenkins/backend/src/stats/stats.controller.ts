import { Controller, Get, Query } from '@nestjs/common';
import { StatsService, StatsQueryParams } from './stats.service';

@Controller('api/stats')
export class StatsController {
  constructor(private statsService: StatsService) {}

  @Get('overall')
  async getOverallStats(@Query() query: StatsQueryParams) {
    return this.statsService.getOverallStats(query);
  }

  @Get('branch-types')
  async getBranchTypeStats() {
    return this.statsService.getBranchTypeStats();
  }

  @Get('daily')
  async getDailyStats(@Query('days') days?: string) {
    const daysNumber = days ? parseInt(days, 10) : 30;
    return this.statsService.getDailyStats(daysNumber);
  }

  @Get('duration-trend')
  async getBuildDurationTrend(@Query('limit') limit?: string) {
    const limitNumber = limit ? parseInt(limit, 10) : 100;
    return this.statsService.getBuildDurationTrend(limitNumber);
  }
}
