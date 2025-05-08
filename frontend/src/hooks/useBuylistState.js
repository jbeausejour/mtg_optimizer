import { useState, useEffect } from "react";

export function useBuylistState() {
  const [selectedBuylist, setSelectedBuylist] = useState(() => {
    const stored = localStorage.getItem("lastSelectedBuylist");
    return stored ? JSON.parse(stored) : null;
  });

  useEffect(() => {
    if (selectedBuylist) {
      localStorage.setItem("lastSelectedBuylist", JSON.stringify(selectedBuylist));
    }
  }, [selectedBuylist]);

  return { selectedBuylist, setSelectedBuylist };
}