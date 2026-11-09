import { UserMenu } from "@/components/auth/user-menu";
import { NotificationBell } from "@/components/notifications/notification-bell";

export function HeaderActions() {
  return (
    <div className="flex items-center gap-1">
      <NotificationBell />
      <UserMenu />
    </div>
  );
}
