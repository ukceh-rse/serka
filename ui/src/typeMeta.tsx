import LayersOutlinedIcon from "@mui/icons-material/LayersOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import ApartmentIcon from "@mui/icons-material/Apartment";
import LabelOutlinedIcon from "@mui/icons-material/LabelOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import type { SvgIconComponent } from "@mui/icons-material";

export type TypeColor =
  | "default"
  | "primary"
  | "secondary"
  | "success"
  | "info"
  | "warning"
  | "error";

// Icon + chip colour per DOO type. The icon next to a result's title and the type
// chip on its right share the same colour so they read as a pair.
const TYPE_META: Record<string, { Icon: SvgIconComponent; color: TypeColor }> =
  {
    "dcat:Dataset": { Icon: LayersOutlinedIcon, color: "primary" },
    "foaf:Person": { Icon: PersonOutlineIcon, color: "info" },
    "foaf:Organization": { Icon: ApartmentIcon, color: "secondary" },
    "skos:Concept": { Icon: LabelOutlinedIcon, color: "success" },
    "fabio:Expression": { Icon: ArticleOutlinedIcon, color: "warning" },
  };

export const typeMeta = (type: string) =>
  TYPE_META[type] ?? { Icon: HelpOutlineIcon, color: "default" as TypeColor };

/** The type's icon, coloured to match its TypeChip. */
export function TypeIcon({
  type,
  fontSize = "1.15rem",
}: {
  type: string;
  fontSize?: string;
}) {
  const { Icon, color } = typeMeta(type);
  return (
    <Icon
      sx={{
        fontSize,
        flexShrink: 0,
        color: color === "default" ? "text.secondary" : `${color}.main`,
      }}
    />
  );
}
