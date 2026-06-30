package com.ResearchBuddy.AIproject.service;

import java.time.ZoneOffset;
import java.util.Collections;
import java.util.List;

import org.springframework.stereotype.Component;

import com.ResearchBuddy.AIproject.persistence.dto.AnalystInsightsResponse;
import com.ResearchBuddy.AIproject.persistence.dto.FactCheckResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ReportMetadataResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchReportResponse;
import com.ResearchBuddy.AIproject.persistence.dto.SourceResponse;
import com.ResearchBuddy.AIproject.persistence.dto.enums.ConfidenceLabelType;
import com.ResearchBuddy.AIproject.persistence.entity.ResearchReportEntity;
import com.ResearchBuddy.AIproject.persistence.entity.SourceEntity;

import lombok.RequiredArgsConstructor;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

@Component
@RequiredArgsConstructor
public class ResearchReportMapper {

  private static final TypeReference<List<String>> STRING_LIST_TYPE = new TypeReference<>() {
  };

  private final ObjectMapper objectMapper;

  public ResearchReportResponse toResponse(ResearchReportEntity report, List<SourceEntity> sources) {
    return ResearchReportResponse.builder()
        .reportId(report.getId())
        .jobId(report.getJob().getId())
        .query(report.getJob().getQuery())
        .domain(report.getJob().getDomain())
        .depth(report.getJob().getDepth())
        .summary(report.getSummary())
        .keyFindings(parseKeyFindings(report.getKeyFindings()))
        .sources(mapSources(sources))
        .factCheck(toFactCheck(report))
        .analystInsights(parseAnalystInsights(report.getAnalystInsights()))
        .metadata(toMetadata(report))
        .createdAt(report.getCreatedAt().atZone(ZoneOffset.UTC).toInstant())
        .build();
  }

  private List<String> parseKeyFindings(String keyFindingsJson) {
    if (keyFindingsJson == null || keyFindingsJson.isBlank()) {
      return List.of();
    }
    try {
      return objectMapper.readValue(keyFindingsJson, STRING_LIST_TYPE);
    } catch (Exception ex) {
      return List.of();
    }
  }

  private List<SourceResponse> mapSources(List<SourceEntity> sources) {
    if (sources == null || sources.isEmpty()) {
      return Collections.emptyList();
    }
    return sources.stream()
        .map(this::toSourceResponse)
        .toList();
  }

  private SourceResponse toSourceResponse(SourceEntity source) {
    return SourceResponse.builder()
        .url(source.getUrl())
        .title(source.getTitle())
        .domainName(source.getDomainName())
        .scrapeStatus(source.getScrapeStatus())
        .sourceSummary(source.getSummary())
        .contentLengthChars(source.getContentLength())
        .build();
  }

  private ReportMetadataResponse toMetadata(ResearchReportEntity report) {
    return ReportMetadataResponse.builder()
        .totalSourcesFound(report.getTotalSourcesFound())
        .totalSourcesProcessed(report.getTotalSourcesProcessed())
        .totalTimeMs(report.getTotalTimeMs() == null ? null : report.getTotalTimeMs().longValue())
        .build();
  }

  private FactCheckResponse toFactCheck(ResearchReportEntity report) {
    if (report.getConfidenceScore() == null && report.getFactCheckVerdict() == null) {
      return null;
    }
    return FactCheckResponse.builder()
        .confidenceScore(report.getConfidenceScore())
        .confidenceLabel(toConfidenceLabel(report))
        .verdict(report.getFactCheckVerdict())
        .build();
  }

  private ConfidenceLabelType toConfidenceLabel(ResearchReportEntity report) {
    if (report.getConfidenceScore() == null) {
      return null;
    }
    double score = report.getConfidenceScore().doubleValue();
    if (score >= 0.8) {
      return ConfidenceLabelType.HIGH;
    }
    if (score >= 0.5) {
      return ConfidenceLabelType.MEDIUM;
    }
    return ConfidenceLabelType.LOW;
  }

  private AnalystInsightsResponse parseAnalystInsights(String analystInsightsJson) {
    if (analystInsightsJson == null || analystInsightsJson.isBlank()) {
      return null;
    }
    try {
      return objectMapper.readValue(analystInsightsJson, AnalystInsightsResponse.class);
    } catch (Exception ex) {
      return null;
    }
  }
}
