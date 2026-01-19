'use client'

import { useState } from 'react'

interface TradeModalProps {
    isOpen: boolean
    onClose: () => void
    tradeType: 'buy' | 'sell'
    initialSymbol?: string
    initialAmount?: string
    prices: Record<string, { name: string; price: number }> | undefined
    onTrade: (type: 'buy' | 'sell', symbol: string, amount: number) => void
    isPending: boolean
}

export function TradeModal({
    isOpen,
    onClose,
    tradeType,
    initialSymbol = '',
    initialAmount = '',
    prices,
    onTrade,
    isPending,
}: TradeModalProps) {
    const [symbol, setSymbol] = useState(initialSymbol)
    const [amount, setAmount] = useState(initialAmount)

    // 当 props 变化时重置状态
    if (initialSymbol !== symbol && initialSymbol) {
        setSymbol(initialSymbol)
    }
    if (initialAmount !== amount && initialAmount) {
        setAmount(initialAmount)
    }

    if (!isOpen) return null

    const handleSubmit = () => {
        onTrade(tradeType, symbol, parseFloat(amount))
    }

    return (
        <div className="dialog-overlay" onClick={onClose}>
            <div className="dialog-content" onClick={e => e.stopPropagation()}>
                <h3 className="text-lg font-semibold mb-4">
                    {tradeType === 'buy' ? '📈 买入确认' : '📉 卖出确认'}
                </h3>
                <div className="space-y-4">
                    <div>
                        <label className="label">标的</label>
                        <select
                            className="input mt-1"
                            value={symbol}
                            onChange={e => setSymbol(e.target.value)}
                        >
                            <option value="">请选择</option>
                            {prices && Object.entries(prices).map(([code, info]) => (
                                <option key={code} value={code}>
                                    {code} - {info.name} (¥{info.price})
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="label">
                            {tradeType === 'buy' ? '买入金额 (元)' : '卖出数量 (股)'}
                        </label>
                        <input
                            type="number"
                            className="input mt-1"
                            value={amount}
                            onChange={e => setAmount(e.target.value)}
                        />
                    </div>
                    <div className="flex gap-3">
                        <button className="btn btn-secondary flex-1" onClick={onClose}>
                            取消
                        </button>
                        <button
                            className={`btn flex-1 ${tradeType === 'buy' ? 'btn-primary' : 'btn-destructive'}`}
                            onClick={handleSubmit}
                            disabled={isPending || !symbol || !amount}
                        >
                            {isPending ? '处理中...' : '确认'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
