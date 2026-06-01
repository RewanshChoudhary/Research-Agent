package com.ResearchBuddy.AIproject.persistence.dto;

import com.ResearchBuddy.AIproject.persistence.dto.enums.AgentNameType;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(Include.NON_NULL)
public class AgentMetricResponse {

  @NotNull
  private AgentNameType agentName;

  @PositiveOrZero
  private Long durationMs;

  @PositiveOrZero
  private Integer llmCallsMade;

  @PositiveOrZero
  private Integer tokensUsed;

  @NotNull
  private Boolean success;
}
