import { geoMercator, geoPath } from "d3-geo";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { classFor, tokenVar, type ScaleClass } from "../colors";
import { useWidth } from "../hooks";

type Ring = number[][];

/** Signed planar area (lon/lat); > 0 means counter-clockwise. */
function ringArea(ring: Ring): number {
  let a = 0;
  for (let i = 0, n = ring.length; i < n; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % n];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}

/** d3-geo wants exterior rings clockwise and holes counter-clockwise (spherical convention). */
function rewind(fc: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection {
  const fixPoly = (poly: Ring[]) =>
    poly.map((ring, i) => {
      const ccw = ringArea(ring) > 0;
      return (i === 0 && ccw) || (i > 0 && !ccw) ? [...ring].reverse() : ring;
    });
  return {
    ...fc,
    features: fc.features.map((f) => {
      const g = f.geometry;
      if (g.type === "Polygon") return { ...f, geometry: { ...g, coordinates: fixPoly(g.coordinates as Ring[]) } };
      if (g.type === "MultiPolygon")
        return { ...f, geometry: { ...g, coordinates: (g.coordinates as Ring[][]).map(fixPoly) } };
      return f;
    }),
  };
}

export interface MapDatum {
  slug: string;
  name: string;
  value: number | null; // drives the colour
  lines: { label: string; value: string }[]; // tooltip content
}

interface Props {
  geojson: GeoJSON.FeatureCollection;
  data: Record<string, MapDatum>;
  scale: ScaleClass[];
  ariaLabel: string;
  linkQuery?: string;
}

export function ChoroplethMap({ geojson, data, scale, ariaLabel, linkQuery }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<{ slug: string; x: number; y: number } | null>(null);
  const navigate = useNavigate();
  const height = Math.round(width * 0.82);

  const fc = useMemo(() => rewind(geojson), [geojson]);
  const { shapes, centroids } = useMemo(() => {
    const projection = geoMercator().fitExtent(
      [
        [8, 8],
        [width - 8, height - 8],
      ],
      fc,
    );
    const path = geoPath(projection);
    const shapes = fc.features.map((f) => ({ slug: String(f.properties?.slug), d: path(f) ?? "" }));
    const centroids = Object.fromEntries(fc.features.map((f) => [String(f.properties?.slug), path.centroid(f)]));
    return { shapes, centroids };
  }, [fc, width, height]);

  const tip = active ? data[active.slug] : undefined;
  return (
    <div className="map-wrap" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={ariaLabel}>
        {shapes.map(({ slug, d }) => {
          const datum = data[slug];
          const cls = classFor(scale, datum?.value);
          const label = datum ? `${datum.name}: ${datum.lines.map((l) => `${l.label} ${l.value}`).join(", ")}` : slug;
          return (
            <path
              key={slug}
              d={d}
              className={`district-shape${active?.slug === slug ? " active" : ""}`}
              fill={cls ? tokenVar(cls.token) : "var(--grid)"}
              tabIndex={0}
              role="link"
              aria-label={label}
              onPointerMove={(e) => {
                const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                setActive({ slug, x: ((e.clientX - r.left) / r.width) * width, y: ((e.clientY - r.top) / r.height) * height });
              }}
              onPointerLeave={() => setActive(null)}
              onFocus={() => {
                const [cx, cy] = centroids[slug] ?? [width / 2, height / 2];
                setActive({ slug, x: cx, y: cy });
              }}
              onBlur={() => setActive(null)}
              onClick={() => navigate(`/district/${slug}${linkQuery ? `?${linkQuery}` : ""}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/district/${slug}${linkQuery ? `?${linkQuery}` : ""}`);
                }
              }}
            />
          );
        })}
      </svg>
      {active && tip && (
        <div className="tooltip" role="status" style={{ left: Math.min(Math.max(active.x, 100), width - 100), top: active.y }}>
          <div className="tt-title">{tip.name}</div>
          {tip.lines.map((l) => (
            <div className="tt-row" key={l.label}>
              <span>{l.label}</span>
              <strong>{l.value}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ScaleLegend({ scale, title }: { scale: ScaleClass[]; title: string }) {
  return (
    <div>
      <div className="small muted">{title}</div>
      <ul className="scale-legend">
        {scale.map((c) => (
          <li key={c.token}>
            <span className="swatch" style={{ background: tokenVar(c.token) }} aria-hidden="true" />
            <span>{c.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
