import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { JenkinsService } from './jenkins.service';

@Injectable()
export class JenkinsScheduler {
  private readonly logger = new Logger(JenkinsScheduler.name);

  constructor(private jenkinsService: JenkinsService) {}

  // Run every 5 minutes
  @Cron(CronExpression.EVERY_5_MINUTES)
  async handleRecentBuildsScraping() {
    this.logger.log('Running scheduled recent builds scraping...');
    try {
      await this.jenkinsService.scrapeRecentBuilds(100);
      this.logger.log('Scheduled scraping completed successfully');
    } catch (error) {
      this.logger.error(`Scheduled scraping failed: ${error.message}`);
    }
  }
}
