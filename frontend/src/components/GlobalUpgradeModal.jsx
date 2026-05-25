import React from "react";
import { UpgradeModal } from "./UpgradeModal";
import { useQuota } from "../lib/quota";

/** Global-scope wrapper so any component can trigger the upgrade modal
 *  via `useQuota().showUpgrade()`. */
export const GlobalUpgradeModal = () => {
  const { upgradeOpen, closeUpgrade, quota } = useQuota();
  return (
    <UpgradeModal open={upgradeOpen} onClose={closeUpgrade} quota={quota} />
  );
};
