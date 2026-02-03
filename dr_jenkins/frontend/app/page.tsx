"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BuildList } from "@/components/build-list";
import { StatsDashboard } from "@/components/stats-dashboard";
import { StatusDashboard } from "@/components/status-dashboard";
import { Button } from "@/components/ui/button";
import { scrapeApi, jobsApi, Job } from "@/lib/api";
import { RefreshCw, Download } from "lucide-react";
import { useState, useEffect } from "react";

export default function Home() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>("docker-all");
  const [isScrapingRecent, setIsScrapingRecent] = useState(false);
  const [isScrapingInitial, setIsScrapingInitial] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const fetchedJobs = await jobsApi.getJobs();
      setJobs(fetchedJobs);
      if (fetchedJobs.length > 0 && !selectedJobId) {
        setSelectedJobId(fetchedJobs[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
    }
  };

  const selectedJob = jobs.find(job => job.id === selectedJobId);

  const handleScrapeRecent = async () => {
    setIsScrapingRecent(true);
    try {
      await scrapeApi.scrapeRecent(selectedJobId);
      alert("Recent builds scraped successfully!");
      window.location.reload();
    } catch (error) {
      alert("Failed to scrape recent builds");
    } finally {
      setIsScrapingRecent(false);
    }
  };

  const handleScrapeInitial = async () => {
    if (!confirm("This will scrape all historical builds. This may take a while. Continue?")) {
      return;
    }
    setIsScrapingInitial(true);
    try {
      await scrapeApi.scrapeInitial(selectedJobId);
      alert("Initial scraping started in background. This may take several minutes.");
    } catch (error) {
      alert("Failed to start initial scraping");
    } finally {
      setIsScrapingInitial(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white border-b shadow-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Jenkins Build Dashboard</h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                {selectedJob?.displayName || "Loading..."}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleScrapeRecent}
                disabled={isScrapingRecent}
                className="hover:bg-blue-50"
              >
                {isScrapingRecent ? (
                  <RefreshCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                )}
                Refresh Recent
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleScrapeInitial}
                disabled={isScrapingInitial}
                className="hover:bg-green-50"
              >
                {isScrapingInitial ? (
                  <Download className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                )}
                Scrape All History
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-6">
        {/* Job Selection Tabs */}
        <Tabs
          value={selectedJobId}
          onValueChange={setSelectedJobId}
          className="space-y-4"
        >
          <TabsList className="bg-white shadow-sm">
            {jobs.map(job => (
              <TabsTrigger key={job.id} value={job.id}>
                {job.displayName}
              </TabsTrigger>
            ))}
          </TabsList>

          {jobs.map(job => (
            <TabsContent key={job.id} value={job.id} className="space-y-4">
              {/* Status/Builds/Stats Sub-tabs */}
              <Tabs defaultValue="status" className="space-y-4">
                <TabsList className="bg-white shadow-sm">
                  <TabsTrigger value="status">Status</TabsTrigger>
                  <TabsTrigger value="builds">Builds</TabsTrigger>
                  <TabsTrigger value="stats">Statistics</TabsTrigger>
                </TabsList>

                <TabsContent value="status" className="space-y-4">
                  <StatusDashboard jobId={job.id} />
                </TabsContent>

                <TabsContent value="builds" className="space-y-4">
                  <BuildList jobId={job.id} jobType={job.type} />
                </TabsContent>

                <TabsContent value="stats">
                  <StatsDashboard jobId={job.id} />
                </TabsContent>
              </Tabs>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </main>
  );
}
