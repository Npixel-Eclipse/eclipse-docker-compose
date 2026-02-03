import { Module } from '@nestjs/common';
import { JobsController } from './jobs.controller';
import { JobsService } from './jobs.service';
import { JobBuildsController } from './job-builds.controller';
import { JobBuildsService } from './job-builds.service';
import { DatabaseModule } from '../database/database.module';
import { JenkinsModule } from '../jenkins/jenkins.module';

@Module({
  imports: [DatabaseModule, JenkinsModule],
  controllers: [JobsController, JobBuildsController],
  providers: [JobsService, JobBuildsService],
  exports: [JobsService, JobBuildsService],
})
export class JobsModule {}
