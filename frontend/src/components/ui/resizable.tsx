import { GripVertical, GripHorizontal } from "lucide-react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { cn } from "@/lib/utils";

interface ResizablePanelGroupProps extends Omit<React.ComponentProps<typeof Group>, "orientation"> {
  orientation?: "horizontal" | "vertical";
  direction?: "horizontal" | "vertical";
}

const ResizablePanelGroup = ({
  className,
  orientation,
  direction,
  ...props
}: ResizablePanelGroupProps) => {
  const resolvedOrientation = orientation ?? direction ?? "horizontal";
  return (
    <Group
      orientation={resolvedOrientation}
      className={cn(
        "flex h-full w-full overflow-hidden",
        resolvedOrientation === "vertical" ? "flex-col" : "flex-row",
        className
      )}
      {...props}
    />
  );
};

const ResizablePanel = Panel;

const ResizableHandle = ({
  withHandle,
  className,
  ...props
}: React.ComponentProps<typeof Separator> & {
  withHandle?: boolean;
}) => (
  <Separator
    className={cn(
      "group relative flex items-center justify-center bg-border transition-colors hover:bg-primary/60 active:bg-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-1",
      // Horizontal separation (resizing width left/right):
      "w-1.5 cursor-col-resize data-[separator-orientation=horizontal]:w-1.5 data-[separator-orientation=horizontal]:h-full",
      // Vertical separation (resizing height top/bottom):
      "data-[separator-orientation=vertical]:h-1.5 data-[separator-orientation=vertical]:w-full data-[separator-orientation=vertical]:cursor-row-resize",
      className
    )}
    {...props}
  >
    {withHandle && (
      <div className="z-10 flex size-4 items-center justify-center rounded-sm border border-border bg-card shadow-sm group-hover:border-primary/50 group-hover:text-primary transition-colors">
        <GripVertical className="size-2.5 opacity-60 group-hover:opacity-100" />
      </div>
    )}
  </Separator>
);

export { ResizablePanelGroup, ResizablePanel, ResizableHandle };
