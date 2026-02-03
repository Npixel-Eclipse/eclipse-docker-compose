import { Controller, Get, Param, Query, ParseIntPipe, NotFoundException } from '@nestjs/common';
import { BuildsService, BuildsQueryParams } from './builds.service';
import { JenkinsService } from '../jenkins/jenkins.service';

@Controller('api/builds')
export class BuildsController {
  constructor(
    private buildsService: BuildsService,
    private jenkinsService: JenkinsService,
  ) {}

  @Get()
  async getBuilds(@Query() query: any) {
    // Convert string params to numbers
    const params: BuildsQueryParams = {
      ...query,
      page: query.page ? parseInt(query.page, 10) : undefined,
      limit: query.limit ? parseInt(query.limit, 10) : undefined,
    };
    return this.buildsService.getBuilds(params);
  }

  @Get('stats')
  async getStats() {
    return this.buildsService.getBuildStats();
  }

  @Get(':id')
  async getBuild(@Param('id', ParseIntPipe) id: number) {
    const build = await this.buildsService.getBuildById(id);
    if (!build) {
      throw new NotFoundException(`Build ${id} not found`);
    }
    return build;
  }

  @Get(':id/logs')
  async getBuildLogs(@Param('id', ParseIntPipe) id: number) {
    const build = await this.buildsService.getBuildById(id);
    if (!build) {
      throw new NotFoundException(`Build ${id} not found`);
    }

    // If logs not in database, fetch from Jenkins
    let logs = await this.buildsService.getBuildLogs(id);
    if (!logs) {
      logs = await this.jenkinsService.getBuildLogs(id);
      if (logs) {
        await this.jenkinsService.updateBuildLogs(id);
      }
    }

    return {
      buildId: id,
      logs,
    };
  }
}
