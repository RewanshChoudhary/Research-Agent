package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ResearchDepth;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ResearchDomain;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
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
public class WorkerJobDetailsResponse {

  @NotNull
  private UUID jobId;

  @NotBlank
  private String query;

  @NotNull
  private ResearchDomain domain;

  @NotNull
  private ResearchDepth depth;

  @Builder.Default
  private Boolean factCheckEnabled = Boolean.FALSE;

  @Builder.Default
  @Min(1)
  @Max(20)
  private Integer maxSources = 5;

  @Builder.Default
  private List<String> trustedDomains = new ArrayList<>();

  @Builder.Default
  private List<String> excludeDomains = new ArrayList<>();
}
