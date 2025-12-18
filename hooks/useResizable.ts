import { useState, useCallback, useEffect } from 'react';

export const useResizable = (initialWidths: { [key: string]: number }) => {
    const [widths, setWidths] = useState(initialWidths);
    const [resizingColumn, setResizingColumn] = useState<string | null>(null);
    const [startX, setStartX] = useState(0);
    const [startWidth, setStartWidth] = useState(0);

    const handleMouseDown = useCallback((e: React.MouseEvent, columnId: string) => {
        e.preventDefault();
        setResizingColumn(columnId);
        setStartX(e.clientX);
        setStartWidth(widths[columnId]);
        document.body.style.cursor = 'col-resize';
    }, [widths]);

    const handleMouseMove = useCallback((e: MouseEvent) => {
        if (resizingColumn) {
            const diff = e.clientX - startX;
            const newWidth = Math.max(50, startWidth + diff); // Minimum width 50px
            setWidths(prev => ({ ...prev, [resizingColumn]: newWidth }));
        }
    }, [resizingColumn, startX, startWidth]);

    const handleMouseUp = useCallback(() => {
        setResizingColumn(null);
        document.body.style.cursor = 'default';
    }, []);

    useEffect(() => {
        if (resizingColumn) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [resizingColumn, handleMouseMove, handleMouseUp]);

    return { widths, handleMouseDown };
};
