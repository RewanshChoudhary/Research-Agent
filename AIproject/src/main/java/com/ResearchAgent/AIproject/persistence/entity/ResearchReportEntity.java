package com.ResearchAgent.AIproject.persistence.entity;

import com.ResearchAgent.AIproject.persistence.entity.enums.OutputFormat;
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
import jakarta.persistence.OneToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.ColumnTransformer;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
@Entity
@Table(name = "research_reports")
public class ResearchReportEntity {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @OneToOne(fetch = FetchType.LAZY, optional = false)
  @JoinColumn(name = "job_id", nullable = false, unique = true)
  private ResearchJobEntity job;

  @ManyToOne(fetch = FetchType.LAZY, optional = false)
  @JoinColumn(name = "user_id", nullable = false)
  private UserEntity user;

  @Column(nullable = false, columnDefinition = "text")
  private String summary;

  @Column(name = "key_findings", nullable = false, columnDefinition = "jsonb")
  @ColumnTransformer(write = "CAST(? AS jsonb)")
  @Builder.Default
  private String keyFindings = "[]";

  @Column(name = "fact_check_verdict", columnDefinition = "text")
  private String factCheckVerdict;

  @Column(name = "confidence_score", precision = 4, scale = 3)
  private BigDecimal confidenceScore;

  @Column(name = "analyst_insights", columnDefinition = "jsonb")
  @ColumnTransformer(write = "CAST(? AS jsonb)")
  private String analystInsights;

  @Enumerated(EnumType.STRING)
  @Column(name = "output_format", nullable = false, length = 20)
  @Builder.Default
  private OutputFormat outputFormat = OutputFormat.JSON;

  @Column(name = "total_sources_found", nullable = false)
  @Builder.Default
  private Integer totalSourcesFound = 0;

  @Column(name = "total_sources_processed", nullable = false)
  @Builder.Default
  private Integer totalSourcesProcessed = 0;

  @Column(name = "total_time_ms", nullable = false)
  @Builder.Default
  private Integer totalTimeMs = 0;

  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  @PrePersist
  void onCreate() {
    if (createdAt == null) {
      createdAt = LocalDateTime.now();
    }
    if (keyFindings == null || keyFindings.isBlank()) {
      keyFindings = "[]";
    }
  }
}
