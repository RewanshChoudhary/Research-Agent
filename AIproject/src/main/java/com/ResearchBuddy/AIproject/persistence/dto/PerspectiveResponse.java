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
public class PerspectiveResponse {

  private String viewpoint;

  private String description;

  @Builder.Default
  private List<String> supportingSourceUrls = new ArrayList<>();
}
