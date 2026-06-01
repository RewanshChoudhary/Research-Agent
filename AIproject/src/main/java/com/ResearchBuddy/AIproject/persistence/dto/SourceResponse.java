package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ScrapeStatus;
import jakarta.validation.constraints.NotBlank;
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
public class SourceResponse {

  @NotBlank
  private String url;

  private String title;

  private String domainName;

  @Builder.Default
  @NotNull
  private Boolean isTrustedSource = Boolean.FALSE;

  @NotNull
  private ScrapeStatus scrapeStatus;

  private String sourceSummary;

  @PositiveOrZero
  private Integer contentLengthChars;
}
