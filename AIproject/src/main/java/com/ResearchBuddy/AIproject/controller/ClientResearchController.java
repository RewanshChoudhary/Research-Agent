package com.ResearchBuddy.AIproject.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.ResearchBuddy.AIproject.persistence.dto.ResearchJobAcceptedResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchJobStatusResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchReportResponse;
import com.ResearchBuddy.AIproject.persistence.dto.ResearchRequest;
import com.ResearchBuddy.AIproject.service.ResearchRequestService;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/research")
public class ClientResearchController {

  private final ResearchRequestService requestService;

  @PostMapping("/send")
  public ResponseEntity<ResearchJobAcceptedResponse> addRequest(@Valid @RequestBody ResearchRequest researchRequest) {
    ResearchJobAcceptedResponse response = requestService.createRequest(researchRequest);
    return ResponseEntity.status(HttpStatus.ACCEPTED)
        .header("Location", response.getPollUrl())
        .body(response);

  }

  @GetMapping("/jobs/{jobId}")
  public ResponseEntity<ResearchJobStatusResponse> fetchResearchStatus(@PathVariable String jobId) {
    return ResponseEntity.ok(requestService.getStatus(jobId));

  }

  @GetMapping("/jobs/{jobId}/report")
  public ResponseEntity<ResearchReportResponse> getResearchReport(@PathVariable String jobId) {
    return ResponseEntity.ok(requestService.getReport(jobId));

  }

}
