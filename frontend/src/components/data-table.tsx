import Link from "next/link";
import { formatMoney, scaled } from "@/lib/money";
import { Invoice, Party } from "@/lib/api";
export function InvoiceTable({items,partyNames={}}:{items:Invoice[];partyNames?:Record<string,string>}) {
  if(!items.length)return <div className="empty">No invoices yet. Create an invoice to get started.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Customer / supplier</th>
            <th>Issue date</th>
            <th>Due date</th>
            <th style={{textAlign:"right"}}>Amount</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map(i=>(
            <tr key={i.id}>
              <td className="td-strong"><Link href={`/invoices/${i.id}`}>{i.invoice_number}</Link></td>
              <td>{partyNames[i.customer_id??i.supplier_id??""]??(i.invoice_type==="outgoing"?"Customer":"Supplier")}</td>
              <td>{i.issue_date}</td>
              <td>{i.due_date}</td>
              <td className="mono" style={{textAlign:"right"}}>
                <div>{i.currency} {formatMoney(String(i.total))}</div>
                {scaled(String(i.paid_amount ?? 0)) > 0n && scaled(String(i.due_amount ?? 0)) > 0n && (
                  <div style={{fontSize:10,color:"#a05e24"}}>
                    Due: {i.currency} {formatMoney(String(i.due_amount))}
                  </div>
                )}
                {i.status === "paid" && (
                  <div style={{fontSize:10,color:"#3d7150"}}>
                    Paid
                  </div>
                )}
              </td>
              <td><span className={`status ${i.status}`}>{i.is_overdue ? "overdue" : i.status.replaceAll("_"," ")}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function PartyTable({items,type}:{items:Party[];type:"customer"|"supplier"}) {if(!items.length)return <div className="empty">No {type}s yet. Add one to keep your records organized.</div>;return <div className="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Location</th><th>VAT number</th></tr></thead><tbody>{items.map(x=><tr key={x.id}><td className="td-strong"><Link href={`/${type==="customer"?"customers":"suppliers"}/${x.id}`}>{x.name}</Link></td><td>{x.email??"—"}</td><td>{x.phone??"—"}</td><td>{[x.city,x.country].filter(Boolean).join(", ")||"—"}</td><td className="mono">{x.vat_number??"—"}</td></tr>)}</tbody></table></div>}
