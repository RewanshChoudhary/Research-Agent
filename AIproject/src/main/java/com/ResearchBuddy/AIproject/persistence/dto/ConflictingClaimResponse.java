package com.ResearchBuddy.AIproject.persistence.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(Include.NON_NULL)
public class ConflictingClaimResponse {

  private String claimA;

  private String claimB;

  private String sourceA;

  private String sourceB;

  private String conflictDescription;
}
