package com.ResearchAgent.AIproject.exception;

import com.ResearchAgent.AIproject.persistence.dto.ApiError;
import com.ResearchAgent.AIproject.persistence.dto.enums.ErrorCodeType;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import lombok.extern.slf4j.Slf4j;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<ApiError> handleValidationException(
      MethodArgumentNotValidException ex,
      HttpServletRequest request) {
    Map<String, String> fieldErrors = ex.getBindingResult()
        .getFieldErrors()
        .stream()
        .collect(Collectors.toMap(
            FieldError::getField,
            error -> defaultMessage(error.getDefaultMessage(), "Invalid value"),
            (first, second) -> first,
            LinkedHashMap::new));

    return buildErrorResponse(
        HttpStatus.BAD_REQUEST,
        ErrorCodeType.VALIDATION_ERROR,
        "Validation failed",
        request,
        fieldErrors);
  }

  @ExceptionHandler(ConstraintViolationException.class)
  public ResponseEntity<ApiError> handleConstraintViolation(
      ConstraintViolationException ex,
      HttpServletRequest request) {
    Map<String, String> violations = ex.getConstraintViolations()
        .stream()
        .collect(Collectors.toMap(
            violation -> violation.getPropertyPath().toString(),
            violation -> defaultMessage(violation.getMessage(), "Invalid value"),
            (first, second) -> first,
            LinkedHashMap::new));

    return buildErrorResponse(
        HttpStatus.BAD_REQUEST,
        ErrorCodeType.VALIDATION_ERROR,
        "Validation failed",
        request,
        violations);
  }

  @ExceptionHandler(IllegalArgumentException.class)
  public ResponseEntity<ApiError> handleIllegalArgumentException(
      IllegalArgumentException ex,
      HttpServletRequest request) {
    return buildErrorResponse(
        HttpStatus.BAD_REQUEST,
        ErrorCodeType.VALIDATION_ERROR,
        defaultMessage(ex.getMessage(), "Bad request"),
        request,
        null);
  }

  @ExceptionHandler(Exception.class)
  public ResponseEntity<ApiError> handleUnexpectedException(
      Exception ex,
      HttpServletRequest request) {
    log.error("Unhandled request exception at {}", request.getRequestURI(), ex);
    return buildErrorResponse(
        HttpStatus.INTERNAL_SERVER_ERROR,
        ErrorCodeType.INTERNAL_SERVER_ERROR,
        "Internal server error",
        request,
        null);
  }

  private ResponseEntity<ApiError> buildErrorResponse(
      HttpStatus status,
      ErrorCodeType errorCode,
      String message,
      HttpServletRequest request,
      Map<String, String> details) {
    ApiError error = ApiError.builder()
        .errorCode(errorCode)
        .message(message)
        .timestamp(java.time.Instant.now())
        .path(request.getRequestURI())
        .details(details == null || details.isEmpty() ? null : details)
        .build();
    return ResponseEntity.status(status).body(error);
  }

  private String defaultMessage(String message, String fallback) {
    if (message == null || message.isBlank()) {
      return fallback;
    }
    return message;
  }
}
