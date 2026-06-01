package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ScrapeStatus;
import jakarta.validation.constraints.NotBlank;
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
public class WorkerSourceItem {

  @NotBlank
  private String url;

  private String title;

  private String domainName;

  @NotNull
  private ScrapeStatus scrapeStatus;

  private Integer contentLength;

  private String summary;

  @Builder.Default
  private Boolean trustedSource = Boolean.FALSE;
}
