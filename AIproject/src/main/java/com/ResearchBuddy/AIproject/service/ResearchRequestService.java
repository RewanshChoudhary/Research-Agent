package com.ResearchBuddy.AIproject.service;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import com.ResearchBuddy.AIproject.persistence.dto.ResearchJobAcceptedResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchJobStatusResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchReportResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchRequest;
import com.ResearchBuddy.AIproject.persistence.dto.JobErrorDetail;
import com.ResearchBuddy.AIproject.persistence.dto.enums.ErrorCodeType;
import com.ResearchBuddy.AIproject.persistence.dto.enums.ResearchStageType;
import com.ResearchBuddy.AIproject.persistence.entity.ResearchJobEntity;
import com.ResearchBuddy.AIproject.persistence.entity.ResearchReportEntity;
import com.ResearchBuddy.AIproject.persistence.entity.UserEntity;
import com.ResearchBuddy.AIproject.persistence.entity.enums.JobStatus;
import com.ResearchBuddy.AIproject.persistence.repository.ResearchJobRepository;
import com.ResearchBuddy.AIproject.persistence.repository.ResearchReportRepository;
import com.ResearchBuddy.AIproject.persistence.repository.SourceRepository;
import com.ResearchBuddy.AIproject.utils.ParsingUtils;

import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import tools.jackson.databind.ObjectMapper;

@Service
@RequiredArgsConstructor
public class ResearchRequestService {
  private final ParsingUtils parsingUtils;

  private final RedisJobPublisherService publisher;
  private final ResearchJobRepository researchJobRepository;
  private final ResearchReportRepository reportRepository;
  private final SourceRepository sourceRepository;
  private final ResearchReportMapper researchReportMapper;
  private final LocalUserService localUserService;
  private final ObjectMapper objectMapper;

  @Transactional
  public ResearchJobAcceptedResponse createRequest(ResearchRequest request) {
    UserEntity user = localUserService.getOrCreateLocalUser();
    ResearchJobEntity job = ResearchJobEntity.builder().user(user)
        .status(JobStatus.PENDING)
        .depth(request.getDepth())
        .maxSources(request.getMaxSources())
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
