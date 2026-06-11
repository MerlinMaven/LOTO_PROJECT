import { useRef } from "react";
import { QRCodeCanvas } from "qrcode.react";
import { Modal } from "./Modal";
import { Button } from "./Button";

interface QRCodeModalProps {
  open: boolean;
  onClose: () => void;
  machineId: string;
  machineName: string;
}

export function QRCodeModal({
  open,
  onClose,
  machineId,
  machineName,
}: QRCodeModalProps) {
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleDownload = () => {
    const canvas = canvasRef.current?.querySelector("canvas");
    if (!canvas) return;
    const url = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = `qr-${machineId}.png`;
    a.click();
  };

  return (
    <Modal
      open={open}
      title={`QR Code — ${machineName}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Fermer
          </Button>
          <Button variant="primary" onClick={handleDownload}>
            Télécharger le QR Code (.png)
          </Button>
        </>
      }
    >
      <div className="flex flex-col items-center gap-4 py-2">
        <div
          ref={canvasRef}
          className="rounded-lg border border-steel-200 bg-white p-4 shadow-sm"
        >
          <QRCodeCanvas
            value={machineId}
            size={220}
            level="H"
            includeMargin={false}
            imageSettings={{
              src: "",
              height: 0,
              width: 0,
              excavate: false,
            }}
          />
        </div>
        <div className="text-center">
          <p className="text-xs font-mono font-semibold text-steel-700">
            {machineId}
          </p>
          <p className="mt-0.5 text-xs text-steel-400">
            Ce QR Code encode uniquement l'identifiant machine.
            <br />
            Imprimez-le et apposez-le sur l'équipement.
          </p>
        </div>
      </div>
    </Modal>
  );
}
