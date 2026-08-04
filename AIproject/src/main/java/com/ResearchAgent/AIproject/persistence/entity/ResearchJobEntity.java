package com.ResearchAgent.AIproject.persistence.entity;

import com.ResearchAgent.AIproject.persistence.entity.enums.JobStatus;
import com.ResearchAgent.AIproject.persistence.entity.enums.ResearchDepth;
import com.ResearchAgent.AIproject.persistence.entity.enums.ResearchDomain;
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
import jakarta.persistence.OneToMany;
import jakarta.persistence.OneToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
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
@Table(name = "research_jobs")
public class ResearchJobEntity {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;
  
  @Column(name = "progress_percent")
@Builder.Default
private Integer progressPercent = 0;

  @ManyToOne(fetch = FetchType.LAZY, optional = false)
  @JoinColumn(name = "user_id", nullable = false)
  private UserEntity user;

  @Column(nullable = false, columnDefinition = "text")
  private String query;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false, length = 50)
  @Builder.Default
  private ResearchDomain domain = ResearchDomain.GENERAL;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false, length = 20)
  @Builder.Default
  private ResearchDepth depth = ResearchDepth.STANDARD;

  @Column(name = "fact_check_enabled", nullable = false)
  private boolean factCheckEnabled;

  @Column(name = "max_sources", nullable = false)
  @Builder.Default
  private Integer maxSources = 10;



  @Enumerated(EnumType.STRING)
  @Column(nullable = false, length = 20)
  @Builder.Default
  private JobStatus status = JobStatus.PENDING;

  @Column(name = "current_stage", length = 50)
  private String currentStage;

  @Column(name = "error_message", columnDefinition = "text")
  private String errorMessage;

  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  @Column(name = "started_at")
  private LocalDateTime startedAt;

  @Column(name = "completed_at")
  private LocalDateTime completedAt;

  @OneToOne(mappedBy = "job", fetch = FetchType.LAZY)
  private ResearchReportEntity report;

  @OneToMany(mappedBy = "job", fetch = FetchType.LAZY)
  @Builder.Default
  
  private List<SourceEntity> sources = new ArrayList<>();

  @OneToMany(mappedBy = "job", fetch = FetchType.LAZY)
  @Builder.Default
  private List<AgentMetricsEntity> agentMetrics = new ArrayList<>();

  @PrePersist
  void onCreate() {
    if (createdAt == null) {
      createdAt = LocalDateTime.now();
    }
    if (status == null) {
      status = JobStatus.PENDING;
    }
  }
}
