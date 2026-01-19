'use client'

import { TradeAction } from '@/hooks/useTrading'

interface RebalanceWizardProps {
    isOpen: boolean
    onClose: () => void
    actions: TradeAction[]
    onExecute: (actions: TradeAction[]) => void
    isPending: boolean
}

export function RebalanceWizard({
    isOpen,
    onClose,
    actions,
    onExecute,
    isPending,
}: RebalanceWizardProps) {
    if (!isOpen) return null

    const executableActions = actions.filter(a => a.action !== 'hold')

    return (
        <div className="dialog-overlay" onClick={onClose}>
            <div className="dialog-content max-w-2xl" onClick={e => e.stopPropagation()}>
                <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                    ⚡ 调仓向导
                </h3>

                <div className="bg-blue-50 p-4 rounded-lg mb-4 text-sm text-blue-800 border border-blue-100">
                    <strong>调仓逻辑：</strong> 系统将根据最新策略信号，自动计算买卖指令。
                    优先执行卖出操作释放资金，随后执行买入操作。
                </div>

                <div className="space-y-4 max-h-[60vh] overflow-y-auto">
                    <h4 className="font-semibold text-gray-700">📋 执行计划预览</h4>
                    <table className="table w-full">
                        <thead>
                            <tr className="bg-gray-50 border-b border-gray-100">
                                <th className="py-2 text-left">操作</th>
                                <th className="py-2 text-left">标的</th>
                                <th className="py-2 text-right">数量/金额</th>
                                <th className="py-2 text-left pl-4">说明</th>
                            </tr>
                        </thead>
                        <tbody>
                            {actions.length === 0 ? (
                                <tr>
                                    <td colSpan={4} className="text-center py-4 text-gray-500">
                                        当前持仓已符合目标，无需调仓 ✅
                                    </td>
                                </tr>
                            ) : (
                                actions.map((action, i) => (
                                    <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                                        <td className="py-3">
                                            <span className={`badge ${action.action === 'buy' ? 'badge-green' : action.action === 'hold' ? 'badge-blue' : 'badge-red'}`}>
                                                {action.action_text}
                                            </span>
                                        </td>
                                        <td className="py-3">
                                            <div className="font-medium">{action.name}</div>
                                            <div className="text-xs text-gray-400 font-mono">{action.code}</div>
                                        </td>
                                        <td className="py-3 text-right font-mono">
                                            {action.action === 'buy' ? `¥${action.amount?.toLocaleString()}` : `${action.shares}股`}
                                        </td>
                                        <td className="py-3 pl-4 text-sm text-gray-500">{action.reason}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="flex gap-4 mt-6 pt-4 border-t border-gray-100">
                    <button className="btn btn-secondary flex-1" onClick={onClose}>
                        {executableActions.length === 0 ? '关闭' : '取消'}
                    </button>
                    {executableActions.length > 0 && (
                        <button
                            className="btn btn-primary flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 border-none relative overflow-hidden"
                            onClick={() => onExecute(executableActions)}
                            disabled={isPending}
                        >
                            {isPending ? (
                                <span className="flex items-center justify-center gap-2">
                                    <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    正在执行...
                                </span>
                            ) : (
                                `确认并执行 (${executableActions.length} 笔交易)`
                            )}
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}
