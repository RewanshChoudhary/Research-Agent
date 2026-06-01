package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ResearchDepth;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ResearchDomain;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(Include.NON_NULL)
public class ResearchReportResponse {

  @NotNull
  private UUID reportId;

  @NotNull
  private UUID jobId;

  @NotBlank
  private String query;

  @NotNull
  private ResearchDomain domain;

  @NotNull
  private ResearchDepth depth;

  @NotBlank
  private String summary;

  @Builder.Default
  @Size(min = 3, max = 7, message = "keyFindings must contain 3 to 7 entries")
  private List<@NotBlank String> keyFindings = new ArrayList<>();

  @Builder.Default
  private List<SourceResponse> sources = new ArrayList<>();

  private FactCheckResponse factCheck;

  private AnalystInsightsResponse analystInsights;

  private ReportMetadataResponse metadata;

  @NotNull
  private Instant createdAt;
}
