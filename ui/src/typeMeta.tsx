import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import ApartmentIcon from "@mui/icons-material/Apartment";
import LabelOutlinedIcon from "@mui/icons-material/LabelOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import PaidOutlinedIcon from "@mui/icons-material/PaidOutlined";
import type { SvgIconComponent } from "@mui/icons-material";

export type TypeColor =
  | "default"
  | "primary"
  | "secondary"
  | "success"
  | "info"
  | "warning"
  | "error";

// Display metadata per DOO type, in results-section order. The icon next to a result's title
// and the type chip on its right share the same colour so they read as a pair.
const TYPE_META: Record<
  string,
  { Icon: SvgIconComponent; color: TypeColor; label: string }
> = {
  "dcat:Dataset": { Icon: StorageOutlinedIcon, color: "primary", label: "Datasets" },
  "foaf:Person": { Icon: PersonOutlineIcon, color: "info", label: "People" },
  "foaf:Organization": { Icon: ApartmentIcon, color: "secondary", label: "Organisations" },
  "frapo:FundingAgency": { Icon: ApartmentIcon, color: "secondary", label: "Funders" },
  "frapo:Grant": { Icon: PaidOutlinedIcon, color: "error", label: "Grants" },
  "skos:Concept": { Icon: LabelOutlinedIcon, color: "success", label: "Concepts" },
  "fabio:Expression": { Icon: ArticleOutlinedIcon, color: "warning", label: "Documents" },
  "fabio:DigitalManifestation": {
    Icon: ArticleOutlinedIcon,
    color: "warning",
    label: "Supporting documents",
  },
};

/** DOO type CURIEs in display order. */
export const TYPE_ORDER = Object.keys(TYPE_META);

export const typeMeta = (type: string) =>
  TYPE_META[type] ?? {
    Icon: HelpOutlineIcon,
    color: "default" as TypeColor,
    label: type,
  };

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
