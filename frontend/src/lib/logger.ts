/**
 * Frontend Structured Logging Utility
 *
 * Mirrors backend's structlog pattern with:
 * - Snake_case event names
 * - Context binding for session/request tracking
 * - Dual output: pretty console in dev, JSON in production
 * - Full type safety with no external dependencies
 *
 * Usage:
 *   const logger = createLogger('ChatComponent')
 *   logger.info('chat_message_sent', { conversation_id: '123', length: 100 })
 *   logger.error('api_request_failed', { endpoint: '/api/chat', status: 500 })
 */

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Log severity levels matching backend structlog levels
 */
export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

/**
 * Common structured log fields (snake_case to match backend)
 */
export interface BaseLogFields {
  // Event identification
  event: string
  level: LogLevel
  timestamp: string
  module: string

  // Request context (bound via bindContext)
  session_id?: string
  conversation_id?: string
  request_id?: string
  user_id?: string

  // Error tracking
  error?: Error
  error_type?: string
  error_message?: string
  stack_trace?: string

  // Performance metrics
  duration_ms?: number
  response_time_ms?: number

  // API calls
  endpoint?: string
  method?: string
  status?: number

  // Additional context
  [key: string]: unknown
}

/**
 * Log entry format for JSON output
 */
interface LogEntry extends BaseLogFields {
  level: LogLevel
}

/**
 * Logger configuration
 */
interface LoggerConfig {
  module: string
  minLevel: LogLevel
  boundContext: Record<string, unknown>
}

// ============================================================================
// Environment & Configuration
// ============================================================================

/**
 * Detect environment from Vite's import.meta.env
 */
const isDevelopment = (): boolean => {
  return import.meta.env.MODE === 'development' || import.meta.env.DEV
}

/**
 * Get minimum log level from environment (defaults to 'info')
 */
const getMinLogLevel = (): LogLevel => {
  const envLevel = import.meta.env.VITE_LOG_LEVEL?.toLowerCase()
  const validLevels: LogLevel[] = ['debug', 'info', 'warn', 'error']
  return validLevels.includes(envLevel as LogLevel) ? (envLevel as LogLevel) : 'info'
}

/**
 * Log level priorities for filtering
 */
const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
}

/**
 * Check if a log level should be emitted
 */
const shouldLog = (level: LogLevel, minLevel: LogLevel): boolean => {
  return LOG_LEVELS[level] >= LOG_LEVELS[minLevel]
}

// ============================================================================
// Formatting & Output
// ============================================================================

/**
 * Format ISO timestamp (matches backend's structlog TimeStamper)
 */
const getTimestamp = (): string => {
  return new Date().toISOString()
}

/**
 * Serialize error objects for structured logging
 */
const serializeError = (error: Error): Record<string, unknown> => {
  return {
    error_type: error.name,
    error_message: error.message,
    stack_trace: error.stack,
  }
}

/**
 * Format log entry for pretty console output (development)
 */
const formatConsoleOutput = (entry: LogEntry): void => {
  const { level, timestamp, module, event, ...fields } = entry

  // Level colors matching structlog's ConsoleRenderer
  const levelColors: Record<LogLevel, string> = {
    debug: '\x1b[36m', // Cyan
    info: '\x1b[32m', // Green
    warn: '\x1b[33m', // Yellow
    error: '\x1b[31m', // Red
  }
  const reset = '\x1b[0m'
  const gray = '\x1b[90m'

  // Format: [TIMESTAMP] LEVEL module event { fields }
  const timeStr = gray + timestamp.split('T')[1].slice(0, 12) + reset
  const levelStr = levelColors[level] + level.toUpperCase().padEnd(5) + reset
  const moduleStr = `${gray}[${module}]${reset}`
  const eventStr = `${event}`

  // Console method based on level
  const consoleMethod = level === 'error' ? console.error : level === 'warn' ? console.warn : console.log

  // Output with structured fields
  if (Object.keys(fields).length > 0) {
    consoleMethod(`${timeStr} ${levelStr} ${moduleStr} ${eventStr}`, fields)
  } else {
    consoleMethod(`${timeStr} ${levelStr} ${moduleStr} ${eventStr}`)
  }
}

/**
 * Format log entry as JSON (production)
 */
const formatJsonOutput = (entry: LogEntry): void => {
  const jsonStr = JSON.stringify(entry)

  // Use appropriate console method for log level
  const consoleMethod = entry.level === 'error' ? console.error : entry.level === 'warn' ? console.warn : console.log

  consoleMethod(jsonStr)
}

/**
 * Emit log entry to console with appropriate formatting
 */
const emitLog = (entry: LogEntry): void => {
  if (isDevelopment()) {
    formatConsoleOutput(entry)
  } else {
    formatJsonOutput(entry)
  }
}

// ============================================================================
// Logger Implementation
// ============================================================================

/**
 * Structured logger instance
 */
export class Logger {
  private config: LoggerConfig

  constructor(module: string, minLevel?: LogLevel) {
    this.config = {
      module,
      minLevel: minLevel ?? getMinLogLevel(),
      boundContext: {},
    }
  }

  /**
   * Bind persistent context to all future log entries
   * (e.g., session_id, conversation_id)
   *
   * @example
   *   logger.bindContext({ session_id: '123', user_id: '456' })
   *   logger.info('user_action') // Will include session_id and user_id
   */
  bindContext(context: Record<string, unknown>): Logger {
    this.config.boundContext = { ...this.config.boundContext, ...context }
    return this
  }

  /**
   * Create a new logger with additional bound context
   * (does not mutate original logger)
   *
   * @example
   *   const requestLogger = logger.withContext({ request_id: '789' })
   *   requestLogger.info('api_call_started')
   */
  withContext(context: Record<string, unknown>): Logger {
    const newLogger = new Logger(this.config.module, this.config.minLevel)
    newLogger.config.boundContext = { ...this.config.boundContext, ...context }
    return newLogger
  }

  /**
   * Clear all bound context
   */
  clearContext(): Logger {
    this.config.boundContext = {}
    return this
  }

  /**
   * Build complete log entry with merged context
   */
  private buildEntry(level: LogLevel, event: string, fields: Record<string, unknown> = {}): LogEntry {
    // Process error objects if present
    let processedFields = { ...fields }
    if (fields.error instanceof Error) {
      const { error, ...rest } = fields
      processedFields = {
        ...rest,
        ...serializeError(error),
      }
    }

    return {
      event,
      level,
      timestamp: getTimestamp(),
      module: this.config.module,
      ...this.config.boundContext,
      ...processedFields,
    }
  }

  /**
   * Log at debug level
   */
  debug(event: string, fields?: Record<string, unknown>): void {
    if (!shouldLog('debug', this.config.minLevel)) return
    const entry = this.buildEntry('debug', event, fields)
    emitLog(entry)
  }

  /**
   * Log at info level
   */
  info(event: string, fields?: Record<string, unknown>): void {
    if (!shouldLog('info', this.config.minLevel)) return
    const entry = this.buildEntry('info', event, fields)
    emitLog(entry)
  }

  /**
   * Log at warn level
   */
  warn(event: string, fields?: Record<string, unknown>): void {
    if (!shouldLog('warn', this.config.minLevel)) return
    const entry = this.buildEntry('warn', event, fields)
    emitLog(entry)
  }

  /**
   * Log at error level
   */
  error(event: string, fields?: Record<string, unknown>): void {
    if (!shouldLog('error', this.config.minLevel)) return
    const entry = this.buildEntry('error', event, fields)
    emitLog(entry)
  }

  /**
   * Get current module name
   */
  getModule(): string {
    return this.config.module
  }

  /**
   * Get current bound context
   */
  getContext(): Record<string, unknown> {
    return { ...this.config.boundContext }
  }
}

// ============================================================================
// Factory Function
// ============================================================================

/**
 * Create a new structured logger instance
 *
 * @param module - Module or component name (e.g., 'ChatComponent', 'api/chat')
 * @param minLevel - Optional minimum log level (defaults to VITE_LOG_LEVEL or 'info')
 *
 * @example
 *   const logger = createLogger('ChatPage')
 *   logger.info('page_mounted', { route: '/chat/123' })
 *
 *   // With context binding
 *   logger.bindContext({ session_id: sessionId })
 *   logger.info('message_sent', { length: 100 })
 */
export const createLogger = (module: string, minLevel?: LogLevel): Logger => {
  return new Logger(module, minLevel)
}

// ============================================================================
// Global Logger Instance
// ============================================================================

/**
 * Default logger instance for general use
 */
export const logger = createLogger('app')

// ============================================================================
// Performance Logging Utilities
// ============================================================================

/**
 * Measure and log function execution time
 *
 * @example
 *   const result = await measureAsync('fetch_user_data', async () => {
 *     return await fetchUser(userId)
 *   }, logger)
 */
export const measureAsync = async <T>(
  event: string,
  fn: () => Promise<T>,
  loggerInstance: Logger = logger,
  fields?: Record<string, unknown>
): Promise<T> => {
  const startTime = performance.now()
  try {
    const result = await fn()
    const duration = Math.round(performance.now() - startTime)
    loggerInstance.info(event, { ...fields, duration_ms: duration, success: true })
    return result
  } catch (error) {
    const duration = Math.round(performance.now() - startTime)
    loggerInstance.error(event, {
      ...fields,
      duration_ms: duration,
      success: false,
      error: error instanceof Error ? error : new Error(String(error)),
    })
    throw error
  }
}

/**
 * Measure synchronous function execution time
 */
export const measureSync = <T>(
  event: string,
  fn: () => T,
  loggerInstance: Logger = logger,
  fields?: Record<string, unknown>
): T => {
  const startTime = performance.now()
  try {
    const result = fn()
    const duration = Math.round(performance.now() - startTime)
    loggerInstance.info(event, { ...fields, duration_ms: duration, success: true })
    return result
  } catch (error) {
    const duration = Math.round(performance.now() - startTime)
    loggerInstance.error(event, {
      ...fields,
      duration_ms: duration,
      success: false,
      error: error instanceof Error ? error : new Error(String(error)),
    })
    throw error
  }
}
