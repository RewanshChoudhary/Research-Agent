package com.ResearchAgent.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchAgent.AIproject.persistence.entity.enums.JobStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(Include.NON_NULL)
public class WorkerStatusUpdateRequest {

  @NotNull
  private JobStatus status;

  private String currentStage;

  @Min(0)
  @Max(100)
  private Integer progressPercent;
}
