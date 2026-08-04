package com.ResearchAgent.AIproject.persistence.dto;

import com.ResearchAgent.AIproject.persistence.dto.enums.ErrorCodeType;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;
import java.time.Instant;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(Include.NON_NULL)
public class JobErrorDetail {

  private ErrorCodeType errorCode;

  private String message;

  private String suggestion;

  private Instant timestamp;
}
