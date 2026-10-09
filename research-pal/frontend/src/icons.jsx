import {
  ArrowRight,
  ArrowSquareOut,
  ArrowUp,
  ArrowsClockwise,
  BookOpen,
  ChartBar,
  ChatCircleText,
  CheckCircle,
  DownloadSimple,
  Flag,
  FileText,
  FunnelSimple,
  Graph,
  Lock,
  MagnifyingGlass,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  CornersOut,
  Monitor,
  Moon,
  Plus,
  Question,
  ShieldCheck,
  SidebarSimple,
  SlidersHorizontal,
  SignOut,
  Sparkle,
  Stack,
  Sun,
  Target,
  Trash,
  UploadSimple,
  Warning,
  X,
} from "@phosphor-icons/react";
import mark from "./assets/mark.png";

// One icon family for the whole app: Phosphor, regular weight. The names below are the names that the components use.
const ICONS = {
  zoomin: MagnifyingGlassPlus,
  zoomout: MagnifyingGlassMinus,
  fit: CornersOut,
  doc: FileText,
  search: MagnifyingGlass,
  chat: ChatCircleText,
  plus: Plus,
  graph: Graph,
  sliders: SlidersHorizontal,
  target: Target,
  upload: UploadSimple,
  download: DownloadSimple,
  check: CheckCircle,
  trash: Trash,
  external: ArrowSquareOut,
  refresh: ArrowsClockwise,
  sparkle: Sparkle,
  x: X,
  logout: SignOut,
  lock: Lock,
  shield: ShieldCheck,
  help: Question,
  flag: Flag,
  layers: Stack,
  chart: ChartBar,
  alert: Warning,
  arrow: ArrowRight,
  arrowup: ArrowUp,
  filter: FunnelSimple,
  sun: Sun,
  moon: Moon,
  monitor: Monitor,
  book: BookOpen,
  sidebar: SidebarSimple,
};

export function Icon({ name, size = 18, className = "" }) {
  const Glyph = ICONS[name];
  if (!Glyph) return null;
  return <Glyph className={"icon " + className} size={size} weight="regular" aria-hidden="true" />;
}

// App mark: the Research Pal icon (chat bubble with a magnifier), cropped to the symbol.
export function Logo({ size = 28 }) {
  return <img className="logo" src={mark} width={size} height={size} alt="" aria-hidden="true" draggable="false" style={{ borderRadius: size * 0.225 }} />;
}
