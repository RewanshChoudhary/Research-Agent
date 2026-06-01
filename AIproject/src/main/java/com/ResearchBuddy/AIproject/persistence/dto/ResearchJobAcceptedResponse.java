package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchBuddy.AIproject.persistence.entity.enums.JobStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.Instant;
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
public class ResearchJobAcceptedResponse {

  @NotNull
  private UUID jobId;

  @Builder.Default
  @NotNull
  private JobStatus status = JobStatus.PENDING;

  @Builder.Default
  @NotNull
  @Positive
  private Integer estimatedTimeSeconds = 30;

  @NotBlank
  private String pollUrl;

  @Builder.Default
  @NotNull
  private Instant createdAt = Instant.now();
}
