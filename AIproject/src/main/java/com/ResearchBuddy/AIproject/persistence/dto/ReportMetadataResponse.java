package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import jakarta.validation.constraints.PositiveOrZero;
import java.util.ArrayList;
import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(Include.NON_NULL)
public class ReportMetadataResponse {

  @PositiveOrZero
  private Integer totalSourcesFound;

  @PositiveOrZero
  private Integer totalSourcesProcessed;

  @PositiveOrZero
  private Integer totalSourcesFailed;

  @PositiveOrZero
  private Integer cacheHits;

  @PositiveOrZero
  private Integer totalLlmCalls;

  @PositiveOrZero
  private Integer totalTokensUsed;

  @PositiveOrZero
  private Long totalTimeMs;

  @Builder.Default
  private List<AgentMetricResponse> agentBreakdown = new ArrayList<>();
}
