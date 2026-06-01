package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
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
public class AnalystInsightsResponse {

  @Builder.Default
  private List<String> patterns = new ArrayList<>();

  @Builder.Default
  private List<PerspectiveResponse> perspectives = new ArrayList<>();

  @Builder.Default
  private List<String> knowledgeGaps = new ArrayList<>();

  @Builder.Default
  private List<String> furtherReadingSuggestions = new ArrayList<>();
}
