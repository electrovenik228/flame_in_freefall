import { CustomChart, ScatterChart } from "echarts/charts";
import { GridComponent, MarkAreaComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef, useState } from "react";

echarts.use([CustomChart, ScatterChart, GridComponent, MarkAreaComponent, TooltipComponent, CanvasRenderer]);

export type ChartOption = echarts.EChartsCoreOption;

export interface ThemeColors {
  dark: boolean;
  text: string;
  muted: string;
  line: string;
  surface: string;
  warm: string;
}

function readColors(): ThemeColors {
  const style = getComputedStyle(document.documentElement);
  const rgb = (name: string) => `rgb(${style.getPropertyValue(`--${name}`).trim().split(" ").join(", ")})`;
  return {
    dark: document.documentElement.classList.contains("dark"),
    text: rgb("text"),
    muted: rgb("muted"),
    line: rgb("line"),
    surface: rgb("surface"),
    warm: rgb("warm"),
  };
}

/** Chart colours follow the theme tokens and update when the theme is switched. */
export function useThemeColors(): ThemeColors {
  const [colors, setColors] = useState(readColors);
  useEffect(() => {
    const observer = new MutationObserver(() => setColors(readColors()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return colors;
}

export function EChart({ option, label, height = 460 }: { option: ChartOption; label: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const resize = new ResizeObserver(() => chart.current?.resize());
    resize.observe(ref.current);
    return () => {
      resize.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);
  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);
  return <div ref={ref} role="img" aria-label={label} style={{ height }} className="w-full" data-testid="chart" />;
}
