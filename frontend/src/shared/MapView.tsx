// Base map: OpenStreetMap tiles with the required attribution. Other layers go inside it.

import "leaflet/dist/leaflet.css";

import type { ReactNode } from "react";
import { MapContainer, TileLayer } from "react-leaflet";

import { JAIPUR_CENTER } from "./mapUtils";

type Props = {
  children?: ReactNode;
  height?: number;
};

export default function MapView({ children, height = 420 }: Props) {
  return (
    <MapContainer
      center={JAIPUR_CENTER}
      zoom={13}
      style={{ height, width: "100%", borderRadius: 6 }}
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors (ODbL). Risk zones: synthetic demo data.'
        maxZoom={19}
      />
      {children}
    </MapContainer>
  );
}
