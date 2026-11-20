import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import ApartmentIcon from "@mui/icons-material/Apartment";
import LabelOutlinedIcon from "@mui/icons-material/LabelOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import PaidOutlinedIcon from "@mui/icons-material/PaidOutlined";
import SchemaOutlinedIcon from "@mui/icons-material/SchemaOutlined";
import type { SvgIconComponent } from "@mui/icons-material";

export type TypeColor =
  | "default"
  | "primary"
  | "secondary"
  | "success"
  | "info"
  | "warning"
  | "error";

export interface TypeMeta {
  Icon: SvgIconComponent;
  color: TypeColor;
  /** Singular, for a type chip. */
  name: string;
  /** Plural, for section headings and the type filter. */
  label: string;
}

// Display metadata per OKF concept type, in type-filter order. The icon next to a result's title
// and the type chip on its right share the same colour so they read as a pair.
const TYPE_META: Record<string, TypeMeta> = {
  dataset: { Icon: StorageOutlinedIcon, color: "primary", name: "Dataset", label: "Datasets" },
  document: { Icon: ArticleOutlinedIcon, color: "warning", name: "Supporting document", label: "Supporting documents" },
  person: { Icon: PersonOutlineIcon, color: "info", name: "Person", label: "People" },
  organisation: { Icon: ApartmentIcon, color: "secondary", name: "Organisation", label: "Organisations" },
  grant: { Icon: PaidOutlinedIcon, color: "error", name: "Grant", label: "Grants" },
  theme: { Icon: LabelOutlinedIcon, color: "success", name: "Theme", label: "Themes" },
  ontology: { Icon: SchemaOutlinedIcon, color: "default", name: "Ontology term", label: "Ontology terms" },
};

const UNKNOWN: TypeMeta = { Icon: HelpOutlineIcon, color: "default", name: "Other", label: "Other" };

/** OKF types in display order. */
export const TYPE_ORDER = Object.keys(TYPE_META);

/** Display metadata for an OKF type; an unknown type gets a generic label and icon. */
export const typeMeta = (type: string): TypeMeta => TYPE_META[type] ?? UNKNOWN;

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
