/**
 * Telegram Auth Extension - Telegram Login Button
 *
 * Ready-to-use Telegram login button component.
 * Just opens Telegram bot - no API calls on click.
 */
import React from "react";
import { Button } from "@/components/ui/button";

// =============================================================================
// TYPES
// =============================================================================

interface TelegramLoginButtonProps {
  /** Click handler - call auth.login() from useTelegramAuth */
  onClick: () => void;
  /** Loading state (for initial session restore) */
  isLoading?: boolean;
  /** Button text */
  buttonText?: string;
  /** CSS class */
  className?: string;
  /** Disabled state */
  disabled?: boolean;
}

// =============================================================================
// SPINNER
// =============================================================================

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

// =============================================================================
// TELEGRAM ICON
// =============================================================================

function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
    >
      <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M8.287 5.906q-1.168.486-4.666 2.01-.567.225-.595.442c-.03.243.275.339.69.47l.175.055c.408.133.958.288 1.243.294q.39.01.868-.32 3.269-2.206 3.374-2.23c.05-.012.12-.026.166.016s.042.12.037.141c-.03.129-1.227 1.241-1.846 1.817-.193.18-.33.307-.358.336a8 8 0 0 1-.188.186c-.38.366-.664.64.015 1.088.327.216.589.393.85.571.284.194.568.387.936.629q.14.092.27.187c.331.236.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.4 1.4 0 0 0-.013-.315.34.34 0 0 0-.114-.217.53.53 0 0 0-.31-.093c-.3.005-.763.166-2.984 1.09" />
    </svg>
  );
}

// =============================================================================
// COMPONENT
// =============================================================================

export function TelegramLoginButton({
  onClick,
  isLoading = false,
  buttonText = "Войти через Telegram",
  className = "",
  disabled = false,
}: TelegramLoginButtonProps): React.ReactElement {
  return (
    <Button
      onClick={onClick}
      disabled={disabled || isLoading}
      className={`bg-[#0088cc] hover:bg-[#0077b5] text-white ${className}`}
    >
      {isLoading ? (
        <Spinner className="!w-5 !h-5 mr-2 flex-shrink-0" />
      ) : (
        <TelegramIcon className="!w-5 !h-5 mr-2 flex-shrink-0" />
      )}
      {isLoading ? "Загрузка..." : buttonText}
    </Button>
  );
}

export default TelegramLoginButton;
