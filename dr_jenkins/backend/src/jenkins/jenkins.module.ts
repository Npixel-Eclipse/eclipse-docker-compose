import { Module } from '@nestjs/common';
import { JenkinsService } from './jenkins.service';
import { JenkinsController } from './jenkins.controller';
import { JenkinsScheduler } from './jenkins.scheduler';
import { DatabaseModule } from '../database/database.module';

@Module({
  imports: [DatabaseModule],
  providers: [JenkinsService, JenkinsScheduler],
  controllers: [JenkinsController],
  exports: [JenkinsService],
})
export class JenkinsModule {}
