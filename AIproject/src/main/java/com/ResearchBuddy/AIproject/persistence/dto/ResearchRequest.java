package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import com.ResearchBuddy.AIproject.persistence.entity.enums.OutputFormat;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ResearchDepth;
import com.ResearchBuddy.AIproject.persistence.entity.enums.ResearchDomain;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
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
public class ResearchRequest {

  @NotBlank(message = "query must not be blank")
  @Size(max = 500, message = "query must be at most 500 characters")
  private String query;

  @Builder.Default
  @NotNull(message = "domain is required")
  private ResearchDomain domain = ResearchDomain.GENERAL;

  @Builder.Default
  @NotNull(message = "depth is required")
  private ResearchDepth depth = ResearchDepth.STANDARD;

  @Builder.Default
  private Boolean factCheck = Boolean.TRUE;

  @Builder.Default
  @NotNull(message = "maxSources is required")
  @Min(value = 1, message = "maxSources must be at least 1")
  @Max(value = 20, message = "maxSources must be at most 20")
  private Integer maxSources = 5;

  @Builder.Default
  @NotNull(message = "outputFormat is required")
  private OutputFormat outputFormat = OutputFormat.JSON;

  @Builder.Default
  @Size(max = 10, message = "trustedDomains can contain at most 10 domains")
  private List<@Size(max = 100, message = "each trusted domain must be at most 100 characters") String>
      trustedDomains = new ArrayList<>();

  @Builder.Default
  @Size(max = 10, message = "excludeDomains can contain at most 10 domains")
  private List<@Size(max = 100, message = "each excluded domain must be at most 100 characters") String>
      excludeDomains = new ArrayList<>();
}
