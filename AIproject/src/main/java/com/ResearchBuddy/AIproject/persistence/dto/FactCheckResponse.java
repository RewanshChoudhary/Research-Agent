package com.ResearchBuddy.AIproject.persistence.dto;

import com.ResearchBuddy.AIproject.persistence.dto.enums.ConfidenceLabelType;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import java.math.BigDecimal;
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
public class FactCheckResponse {

  @NotNull
  @DecimalMin(value = "0.000", inclusive = true)
  @DecimalMax(value = "1.000", inclusive = true)
  @Digits(integer = 1, fraction = 3)
  private BigDecimal confidenceScore;

  @NotNull
  private ConfidenceLabelType confidenceLabel;

  @PositiveOrZero
  private Integer totalClaims;

  @PositiveOrZero
  private Integer verifiedClaims;

  @PositiveOrZero
  private Integer unverifiedClaims;

  @Builder.Default
  private List<ConflictingClaimResponse> conflictingClaims = new ArrayList<>();

  private String verdict;
}
