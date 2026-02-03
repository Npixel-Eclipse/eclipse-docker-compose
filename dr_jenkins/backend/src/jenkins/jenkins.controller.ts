import { Controller, Post, HttpCode, HttpStatus } from '@nestjs/common';
import { JenkinsService } from './jenkins.service';

@Controller('api/scrape')
export class JenkinsController {
  constructor(private jenkinsService: JenkinsService) {}

  @Post('initial')
  @HttpCode(HttpStatus.ACCEPTED)
  async scrapeInitialHistory() {
    // Run in background
    this.jenkinsService.scrapeInitialHistory().catch(err => {
      console.error('Initial scraping failed:', err);
    });

    return {
      message: 'Initial history scraping started in background',
    };
  }

  @Post('recent')
  @HttpCode(HttpStatus.OK)
  async scrapeRecentBuilds() {
    await this.jenkinsService.scrapeRecentBuilds(100);
    return {
      message: 'Recent builds scraped successfully',
    };
  }
}
