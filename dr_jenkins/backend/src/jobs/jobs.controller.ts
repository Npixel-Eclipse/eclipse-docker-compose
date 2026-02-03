import { Controller, Get, Param } from '@nestjs/common';
import { JobsService, JobConfig } from './jobs.service';

@Controller('api/jobs')
export class JobsController {
  constructor(private readonly jobsService: JobsService) {}

  @Get()
  getAllJobs(): JobConfig[] {
    return this.jobsService.getAllJobs();
  }

  @Get(':jobId')
  getJob(@Param('jobId') jobId: string): JobConfig {
    const job = this.jobsService.getJob(jobId);
    if (!job) {
      throw new Error(`Job ${jobId} not found`);
    }
    return job;
  }
}
