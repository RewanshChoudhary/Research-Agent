package com.ResearchAgent.AIproject.service;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;

import com.ResearchAgent.AIproject.persistence.entity.enums.ResearchDepth;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import com.ResearchAgent.AIproject.persistence.dto.ResearchJobAcceptedResponse;
import com.ResearchAgent.AIproject.persistence.dto.ResearchJobStatusResponse;
import com.ResearchAgent.AIproject.persistence.dto.ResearchReportResponse;
import com.ResearchAgent.AIproject.persistence.dto.ResearchRequest;
import com.ResearchAgent.AIproject.persistence.dto.JobErrorDetail;
import com.ResearchAgent.AIproject.persistence.dto.enums.ErrorCodeType;
import com.ResearchAgent.AIproject.persistence.dto.enums.ResearchStageType;
import com.ResearchAgent.AIproject.persistence.entity.ResearchJobEntity;
import com.ResearchAgent.AIproject.persistence.entity.ResearchReportEntity;
import com.ResearchAgent.AIproject.persistence.entity.UserEntity;
import com.ResearchAgent.AIproject.persistence.entity.enums.JobStatus;
import com.ResearchAgent.AIproject.persistence.repository.ResearchJobRepository;
import com.ResearchAgent.AIproject.persistence.repository.ResearchReportRepository;
import com.ResearchAgent.AIproject.persistence.repository.SourceRepository;
import com.ResearchAgent.AIproject.utils.ParsingUtils;

import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import tools.jackson.databind.ObjectMapper;

import static com.ResearchAgent.AIproject.persistence.entity.enums.ResearchDepth.DEEP;
import static com.ResearchAgent.AIproject.persistence.entity.enums.ResearchDepth.QUICK;

@Service
@RequiredArgsConstructor
public class ResearchRequestService {

  private final Environment environment;
  private final ParsingUtils parsingUtils;

  private final RedisJobPublisherService publisher;
  private final ResearchJobRepository researchJobRepository;
  private final ResearchReportRepository reportRepository;
  private final SourceRepository sourceRepository;
  private final ResearchReportMapper researchReportMapper;
  private final LocalUserService localUserService;
  private final ObjectMapper objectMapper;

  private int getMaxSourcesFromDepth(ResearchDepth depth) {
    int quick = Integer.parseInt(
        environment.getProperty("MAX_SOURCES_QUICK", "15"));
    int standard = Integer.parseInt(
        environment.getProperty("MAX_SOURCES_STANDARD", "17"));
    int deep = Integer.parseInt(
        environment.getProperty("MAX_SOURCES_DEEP", "25"));
    return switch (depth) {
      case QUICK -> quick;
      case STANDARD -> standard;
      case DEEP -> deep;
    };
  }

  @Transactional
  public ResearchJobAcceptedResponse createRequest(ResearchRequest request) {
    UserEntity user = localUserService.getOrCreateLocalUser();
    ResearchJobEntity job = ResearchJobEntity.builder().user(user)
        .status(JobStatus.PENDING)
        .depth(request.getDepth())
        .maxSources(request.getMaxSources() != null ? request.getMaxSources() : getMaxSourcesFromDepth(request.getDepth()))
        .domain(request.getDomain())
        .factCheckEnabled(Boolean.TRUE.equals(request.getFactCheck()))
        .query(request.getQuery())
        .build();
    researchJobRepository.save(job);

    TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
      @Override
      public void afterCommit() {
        publisher.publish(job.getId().toString());
      }
    });
    return ResearchJobAcceptedResponse.builder()
        .jobId(job.getId())
        .status(JobStatus.PENDING)
        .estimatedTimeSeconds(30)
        .createdAt(job.getCreatedAt().atZone(ZoneOffset.UTC).toInstant())
        .pollUrl("/api/research/jobs/" + job.getId())
        .build();

  }

  @Transactional
  public ResearchJobStatusResponse getStatus(String jobId) {
    UUID parsedJobId = parsingUtils.parseJobId(jobId);

    ResearchJobEntity job = researchJobRepository.findById(parsedJobId)
        .orElseThrow(() -> new IllegalArgumentException("Job not found"));

    return ResearchJobStatusResponse.builder()
        .jobId(job.getId())
        .status(job.getStatus())
        .query(job.getQuery())
        .domain(job.getDomain())
        .depth(job.getDepth())
        .currentStage(parseStage(job.getCurrentStage()))
        .progressPercent(job.getProgressPercent())
        .createdAt(toInstant(job.getCreatedAt()))
        .startedAt(toInstant(job.getStartedAt()))
        .completedAt(toInstant(job.getCompletedAt()))
        .elapsedTimeMs(elapsedTimeMs(job))
        .report(reportForCompletedJob(job))
        .error(errorForFailedJob(job))
        .build();
  }

  @Transactional
  public ResearchReportResponse getReport(String jobId) {
    UUID parsedJobId = parsingUtils.parseJobId(jobId);
    ResearchReportEntity report = reportRepository.findByJobId(parsedJobId)
        .orElseThrow(() -> new IllegalArgumentException("Report not found"));

    return researchReportMapper.toResponse(report, sourceRepository.findByJobId(parsedJobId));
  }

  private Instant toInstant(java.time.LocalDateTime value) {
    if (value == null) {
      return null;
    }
    return value.atZone(ZoneOffset.UTC).toInstant();
  }

  private ResearchStageType parseStage(String currentStage) {
    if (currentStage == null || currentStage.isBlank()) {
      return null;
    }
    try {
      return ResearchStageType.valueOf(currentStage.trim().toUpperCase());
    } catch (IllegalArgumentException ex) {
      return null;
    }
  }

  private Long elapsedTimeMs(ResearchJobEntity job) {
    if (job.getStartedAt() == null) {
      return null;
    }
    LocalDateTime end = job.getCompletedAt() == null ? LocalDateTime.now() : job.getCompletedAt();
    return Duration.between(job.getStartedAt(), end).toMillis();
  }

  private ResearchReportResponse reportForCompletedJob(ResearchJobEntity job) {
    if (job.getStatus() != JobStatus.COMPLETED) {
      return null;
    }
    return reportRepository.findByJobId(job.getId())
        .map(report -> researchReportMapper.toResponse(report, sourceRepository.findByJobId(job.getId())))
        .orElse(null);
  }

  private JobErrorDetail errorForFailedJob(ResearchJobEntity job) {
    if (job.getStatus() != JobStatus.FAILED) {
      return null;
    }
    return JobErrorDetail.builder()
        .errorCode(ErrorCodeType.INTERNAL_SERVER_ERROR)
        .message(job.getErrorMessage())
        .timestamp(toInstant(job.getCompletedAt()))
        .build();
  }

}
