package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import jakarta.validation.constraints.PositiveOrZero;
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
public class PaginatedReportListResponse {

  @Builder.Default
  private List<ReportSummaryResponse> reports = new ArrayList<>();

  @PositiveOrZero
  private Integer totalCount;

  @PositiveOrZero
  private Integer page;

  @PositiveOrZero
  private Integer pageSize;

  private Boolean hasNextPage;
}
