import React, { useEffect, useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { listPrinters } from "../lib/api";

const FAMILY_LABEL = {
  orca: "OrcaSlicer (Bambu, Sovol, Elegoo, Flashforge, Anycubic, Creality)",
  prusa: "PrusaSlicer (Prusa)",
  super: "SuperSlicer (Voron, Klipper)",
  cura: "Cura (Ultimaker, generic)",
  marlin: "Marlin direct G-code",
};

/** Printer profile dropdown — grouped by slicer family.
 *
 *  Props:
 *    value:    currently selected printer_id
 *    onChange: (printer_id) => void
 *    disabled: boolean
 *    testId:   data-testid prefix (default "printer-select")
 */
export const PrinterSelect = ({
  value,
  onChange,
  disabled,
  testId = "printer-select",
}) => {
  const [printers, setPrinters] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listPrinters()
      .then((data) => {
        if (!cancelled) {
          setPrinters(data);
          setLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = useMemo(() => {
    const out = {};
    for (const p of printers) {
      (out[p.slicer_family] = out[p.slicer_family] || []).push(p);
    }
    return out;
  }, [printers]);

  const current = printers.find((p) => p.id === value);

  return (
    <Select value={value || "generic_orca"} onValueChange={onChange} disabled={disabled || !loaded}>
      <SelectTrigger
        data-testid={testId}
        className="rounded-none bg-zinc-950 border-zinc-800 font-mono text-xs h-9"
      >
        <SelectValue placeholder="Choose printer…" />
      </SelectTrigger>
      <SelectContent className="rounded-none bg-zinc-950 border-zinc-800 max-h-[60vh]">
        {Object.entries(grouped).map(([fam, list]) => (
          <SelectGroup key={fam}>
            <SelectLabel className="font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500 px-2 pt-2">
              {FAMILY_LABEL[fam] || fam}
            </SelectLabel>
            {list.map((p) => (
              <SelectItem
                key={p.id}
                value={p.id}
                data-testid={`${testId}-option-${p.id}`}
                className="font-mono text-xs rounded-none"
              >
                {p.name}
                {p.multi_tool ? " · AMS/MMU" : ""}
              </SelectItem>
            ))}
          </SelectGroup>
        ))}
      </SelectContent>
      {current && (
        <input type="hidden" value={current.id} data-testid={`${testId}-current`} />
      )}
    </Select>
  );
};
