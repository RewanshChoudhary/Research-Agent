package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
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
public class WorkerCompleteRequest {

  @NotBlank
  private String summary;

  @NotNull
  @Size(min = 1)
  private List<@NotBlank String> keyFindings;

  @Builder.Default
  private List<WorkerSourceItem> sources = new ArrayList<>();

  @PositiveOrZero
  private Integer totalSourcesFound;

  @PositiveOrZero
  private Integer totalSourcesProcessed;

  @PositiveOrZero
  private Integer totalTimeMs;

  private FactCheckResponse factCheck;

  private AnalystInsightsResponse analystInsights;
}
