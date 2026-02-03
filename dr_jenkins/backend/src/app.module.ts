import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ScheduleModule } from '@nestjs/schedule';
import { DatabaseModule } from './database/database.module';
import { JenkinsModule } from './jenkins/jenkins.module';
import { BuildsModule } from './builds/builds.module';
import { StatsModule } from './stats/stats.module';
import { JobsModule } from './jobs/jobs.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    ScheduleModule.forRoot(),
    DatabaseModule,
    JobsModule,
    JenkinsModule,
    BuildsModule,
    StatsModule,
  ],
})
export class AppModule {}
