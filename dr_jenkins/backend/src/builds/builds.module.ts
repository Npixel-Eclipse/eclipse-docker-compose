import { Module } from '@nestjs/common';
import { BuildsService } from './builds.service';
import { BuildsController } from './builds.controller';
import { JenkinsModule } from '../jenkins/jenkins.module';

@Module({
  imports: [JenkinsModule],
  providers: [BuildsService],
  controllers: [BuildsController],
})
export class BuildsModule {}
