package com.ResearchBuddy.AIproject.persistence.entity;

import com.ResearchBuddy.AIproject.persistence.entity.enums.ScrapeStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
@Entity
@Table(name = "sources")
public class SourceEntity {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @ManyToOne(fetch = FetchType.LAZY, optional = false)
  @JoinColumn(name = "job_id", nullable = false)
  private ResearchJobEntity job;

  @Column(nullable = false, columnDefinition = "text")
  private String url;

  @Column(length = 500)
  private String title;

  @Column(name = "domain_name", length = 255)
  private String domainName;

  @Enumerated(EnumType.STRING)
  @Builder.Default
  @Column(name = "scrape_status", nullable = false, length = 20)
  private ScrapeStatus scrapeStatus = ScrapeStatus.SKIPPED;

  @Column(name = "content_length")
  private Integer contentLength;

  @Column(columnDefinition = "text")
  private String summary;

  @Column(name = "is_trusted_source", nullable = false)
  private boolean trustedSource;

  @Column(name = "scraped_at")
  private LocalDateTime scrapedAt;
}
