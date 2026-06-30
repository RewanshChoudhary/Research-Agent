package com.ResearchBuddy.AIproject.service;

import com.ResearchBuddy.AIproject.persistence.dto.WorkerCompleteRequest;
import com.ResearchBuddy.AIproject.persistence.dto.WorkerFailRequest;
import com.ResearchBuddy.AIproject.persistence.dto.WorkerJobDetailsResponse;
import com.ResearchBuddy.AIproject.persistence.dto.WorkerStatusUpdateRequest;
import com.ResearchBuddy.AIproject.persistence.entity.ResearchJobEntity;
import com.ResearchBuddy.AIproject.persistence.entity.ResearchReportEntity;
import com.ResearchBuddy.AIproject.persistence.entity.SourceEntity;
import com.ResearchBuddy.AIproject.persistence.entity.enums.JobStatus;
import com.ResearchBuddy.AIproject.persistence.repository.ResearchJobRepository;
import com.ResearchBuddy.AIproject.persistence.repository.ResearchReportRepository;
import com.ResearchBuddy.AIproject.persistence.repository.SourceRepository;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Service
@RequiredArgsConstructor
public class WorkerJobService {

    private final ResearchJobRepository researchJobRepository;
    private final ResearchReportRepository researchReportRepository;
    private final SourceRepository sourceRepository;
    private final ObjectMapper objectMapper;

    @Transactional(readOnly = true)
    public WorkerJobDetailsResponse getJobDetails(UUID jobId) {
        ResearchJobEntity job = researchJobRepository.findById(jobId)
                .orElseThrow(() -> new IllegalArgumentException("Job not found: " + jobId));
        // Only expose fields Python needs to execute research.
        // Omit userId, createdAt, status — worker never needs them.
        // Omit lazy-loaded relations (user, report, sources) to avoid LazyInitializationException.
        return WorkerJobDetailsResponse.builder()
                .jobId(job.getId())
                .query(job.getQuery())
                .domain(job.getDomain())
                .depth(job.getDepth())
                .factCheckEnabled(job.isFactCheckEnabled())
                .maxSources(job.getMaxSources())
                .build();
    }

    @Transactional
    public void updateStatus(UUID jobId, WorkerStatusUpdateRequest body) {
        ResearchJobEntity job = researchJobRepository.findById(jobId)
                .orElseThrow(() -> new IllegalArgumentException("Job not found: " + jobId));
        job.setStatus(body.getStatus());
        job.setCurrentStage(normalizeStage(body.getCurrentStage()));
        job.setProgressPercent(body.getProgressPercent());
        // Only set startedAt on first PROCESSING transition.
        // Worker may reconnect/resend on retry — never overwrite the original start time.
        if (body.getStatus() == JobStatus.PROCESSING && job.getStartedAt() == null) {
            job.setStartedAt(LocalDateTime.now());
        }
    }

    @Transactional
    public void completeJob(UUID jobId, WorkerCompleteRequest body) {
        ResearchJobEntity job = researchJobRepository.findById(jobId)
                .orElseThrow(() -> new IllegalArgumentException("Job not found: " + jobId));

        // @Transactional ensures all 3 writes (job status, report, sources) commit atomically.
        // Worker is fire-and-forget — no response body needed beyond 200 OK.
        job.setStatus(JobStatus.COMPLETED);
        job.setCurrentStage("BUILDING");
        job.setProgressPercent(100);
        job.setCompletedAt(LocalDateTime.now());

        ResearchReportEntity report = ResearchReportEntity.builder()
                .job(job)
                .user(job.getUser())
                .summary(body.getSummary())
                .keyFindings(serializeKeyFindings(body.getKeyFindings()))
                .factCheckVerdict(body.getFactCheck() == null ? null : body.getFactCheck().getVerdict())
                .confidenceScore(toConfidenceScore(body))
                .analystInsights(serializeAnalystInsights(body))
                .totalSourcesFound(body.getTotalSourcesFound())
                .totalSourcesProcessed(body.getTotalSourcesProcessed())
                .totalTimeMs(body.getTotalTimeMs())
                .build();

        researchReportRepository.save(report);

        if (body.getSources() != null && !body.getSources().isEmpty()) {
            List<SourceEntity> sources = body.getSources().stream()
                    .map(item -> SourceEntity.builder()
                            .job(job)
                            .url(item.getUrl())
                            .title(truncate(item.getTitle(), 500))
                            .domainName(truncate(item.getDomainName(), 255))
                            .scrapeStatus(item.getScrapeStatus())
                            .contentLength(item.getContentLength())
                            .summary(item.getSummary())
                            .build())
                    .toList();
            sourceRepository.saveAll(sources);
        }
    }

    @Transactional
    public void failJob(UUID jobId, WorkerFailRequest body) {
        ResearchJobEntity job = researchJobRepository.findById(jobId)
                .orElseThrow(() -> new IllegalArgumentException("Job not found: " + jobId));
        // Set completedAt so client polling sees a terminal state and stops.
        // Without this, client would keep polling indefinitely hoping for recovery.
        job.setStatus(JobStatus.FAILED);
        job.setCompletedAt(LocalDateTime.now());
        job.setErrorMessage(body.getErrorMessage());
    }

    private String serializeKeyFindings(List<String> keyFindings) {
        if (keyFindings == null || keyFindings.isEmpty()) {
            return "[]";
        }
        try {
            return objectMapper.writeValueAsString(keyFindings);
        } catch (Exception e) {
            return "[]";
        }
    }

    private BigDecimal toConfidenceScore(WorkerCompleteRequest body) {
        if (body.getFactCheck() == null || body.getFactCheck().getConfidenceScore() == null) {
            return null;
        }
        BigDecimal score = body.getFactCheck().getConfidenceScore();
        if (score.compareTo(BigDecimal.ZERO) < 0) {
            score = BigDecimal.ZERO;
        }
        if (score.compareTo(BigDecimal.ONE) > 0) {
            score = BigDecimal.ONE;
        }
        return score.setScale(3, RoundingMode.HALF_UP);
    }

    private String serializeAnalystInsights(WorkerCompleteRequest body) {
        if (body.getAnalystInsights() == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(body.getAnalystInsights());
        } catch (Exception e) {
            return null;
        }
    }

    private String normalizeStage(String stage) {
        if (stage == null || stage.isBlank()) {
            return null;
        }
        return stage.trim().toUpperCase();
    }

    private String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }

}
