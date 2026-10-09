// Base map: OpenStreetMap tiles with the required attribution, in a rounded frame.
// Other layers go inside it. In dark mode the tiles are dimmed by CSS (styles/app.css).
// Scroll-wheel zoom is off, so scrolling the page over the map scrolls the page; zoom with the
// + / - buttons, a double-click or a pinch.

import "leaflet/dist/leaflet.css";

import type { ReactNode } from "react";
import { MapContainer, TileLayer } from "react-leaflet";

import { JAIPUR_CENTER } from "./mapUtils";

type Props = {
  children?: ReactNode;
  height?: number;
  label: string; // what the map shows, for screen readers
};

export default function MapView({ children, height = 420, label }: Props) {
  return (
    <div className="map-frame" role="region" aria-label={label}>
      <MapContainer
        center={JAIPUR_CENTER}
        zoom={13}
        scrollWheelZoom={false}
        style={{ height, width: "100%" }}
      >
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors (ODbL). Risk zones: synthetic demo data.'
          maxZoom={19}
        />
        {children}
      </MapContainer>
    </div>
  );
}
