<#
.SYNOPSIS
Reaches the parts of the running Neverwinter Nights Toolset that simulated mouse clicks cannot, for a Toolset check
driven by computer use (tools/envkit/toolset.py, docs/envkit/sheet-runbook.md).

.DESCRIPTION
The Toolset's own windows are TdlgWelcome (the opening dialogue) and TfrmFrame (the editor); its hidden TApplication
window is never acted on. Its palette trees ignore simulated clicks on their expanders, so items are expanded and
selected with tree-view messages. Trees are counted among the frame's visible ones, as -Do expand lists them.

  -Do list                      the Toolset's visible top-level windows
  -Do kids  -Class <class>      the visible child windows of one of them
  -Do front -Class <class>      bring it to the front (do this right before every batch of clicks)
  -Do move  -Class <class>      place and size it (60,40, 2100 by 1250)
  -Do expand -Index <tree>      expand every item of a tree
  -Do reach -Index <tree> -Root <n> -Child <m>
                                collapse the tree's top items, expand the n-th, then show and select its m-th child
                                (Features, Groups and Terrain are the palette's top items, in that order)
  -Do path  -Index <tree> -Path <a/b/c>
                                walk down the tree by item numbers, expanding on the way, then show and select the last
#>
param([string]$Do = 'list', [string]$Class = '', [int]$Index = 0, [int]$Root = 0, [int]$Child = 0, [string]$Path = '')
Add-Type @'
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class Tw {
  public delegate bool Each(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(Each f, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, Each f, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int t, bool r);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public static string Cls(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }
  public static string Txt(IntPtr h) { var s = new StringBuilder(256); GetWindowText(h, s, 256); return s.ToString(); }
  public static List<IntPtr> Top(uint pid) { var a = new List<IntPtr>(); EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid) a.Add(h); return true; }, IntPtr.Zero); return a; }
  public static List<IntPtr> Kids(IntPtr p) { var a = new List<IntPtr>(); EnumChildWindows(p, (h, l) => { a.Add(h); return true; }, IntPtr.Zero); return a; }
  public static void Front(IntPtr h) {
    uint p; uint target = GetWindowThreadProcessId(h, out p); uint fore = GetWindowThreadProcessId(GetForegroundWindow(), out p); uint me = GetCurrentThreadId();
    keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero);
    AttachThreadInput(me, fore, true); AttachThreadInput(me, target, true);
    BringWindowToTop(h); SetForegroundWindow(h);
    AttachThreadInput(me, target, false); AttachThreadInput(me, fore, false);
  }
}
'@
$process = Get-Process nwtoolset -ErrorAction Stop | Select-Object -First 1
$tops = [Tw]::Top([uint32]$process.Id)
function Describe($h) { $r = New-Object Tw+RECT; [void][Tw]::GetWindowRect($h, [ref]$r); '{0} class={1} visible={2} rect={3},{4},{5},{6} text="{7}"' -f $h, [Tw]::Cls($h), [Tw]::IsWindowVisible($h), $r.L, $r.T, $r.R, $r.B, [Tw]::Txt($h) }
switch ($Do) {
  'list' { foreach ($h in $tops) { if ([Tw]::IsWindowVisible($h)) { Describe $h } } }
  'kids' { $w = $tops | Where-Object { [Tw]::Cls($_) -eq $Class -and [Tw]::IsWindowVisible($_) } | Select-Object -First 1; foreach ($k in [Tw]::Kids($w)) { if ([Tw]::IsWindowVisible($k)) { Describe $k } } }
  'front' { $w = $tops | Where-Object { [Tw]::Cls($_) -eq $Class -and [Tw]::IsWindowVisible($_) } | Select-Object -First 1; if (-not $w) { throw "no visible $Class" }; [Tw]::Front($w); Describe $w; 'foreground=' + [Tw]::GetForegroundWindow() }
  'move' { $w = $tops | Where-Object { [Tw]::Cls($_) -eq $Class -and [Tw]::IsWindowVisible($_) } | Select-Object -First 1; [void][Tw]::MoveWindow($w, 60, 40, 2100, 1250, $true); Describe $w }
  'expand' {
    # expand every item of the Index-th visible tree in the frame, as its expanders ignore simulated clicks
    $w = $tops | Where-Object { [Tw]::Cls($_) -eq 'TfrmFrame' -and [Tw]::IsWindowVisible($_) } | Select-Object -First 1
    $trees = @([Tw]::Kids($w) | Where-Object { [Tw]::Cls($_) -like '*TreeView*' -and [Tw]::IsWindowVisible($_) })
    $n = 0; foreach ($t in $trees) { "tree $n : " + (Describe $t); $n++ }
    if ($Index -ge 0 -and $trees.Count -gt $Index) {
      $tree = $trees[$Index]; $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]0, [IntPtr]0); $count = 0  # TVM_GETNEXTITEM, TVGN_ROOT
      while ($item -ne [IntPtr]::Zero) { [void][Tw]::SendMessage($tree, 0x1102, [IntPtr]2, $item); $count++; $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]6, $item) }  # TVM_EXPAND TVE_EXPAND; TVGN_NEXTVISIBLE
      "expanded $count items in tree $Index"
    }
  }
  'path' {
    # in the Index-th visible tree: walk Path (indices joined by /), expanding each item on the way, then show and select the last
    $w = $tops | Where-Object { [Tw]::Cls($_) -eq 'TfrmFrame' -and [Tw]::IsWindowVisible($_) } | Select-Object -First 1
    $trees = @([Tw]::Kids($w) | Where-Object { [Tw]::Cls($_) -like '*TreeView*' -and [Tw]::IsWindowVisible($_) })
    $n = 0; foreach ($t in $trees) { "tree $n : " + (Describe $t); $n++ }
    $tree = $trees[$Index]; $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]0, [IntPtr]0); $steps = @($Path -split '/' | ForEach-Object { [int]$_ })
    for ($depth = 0; $depth -lt $steps.Count; $depth++) {
      $all = 0; $walk = $item; while ($walk -ne [IntPtr]::Zero) { $all++; $walk = [Tw]::SendMessage($tree, 0x110A, [IntPtr]1, $walk) }
      for ($i = 0; $i -lt $steps[$depth] -and $item -ne [IntPtr]::Zero; $i++) { $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]1, $item) }
      "depth $depth : $all items, took $($steps[$depth])"
      if ($item -eq [IntPtr]::Zero) { throw 'no such item' }
      if ($depth -lt $steps.Count - 1) { [void][Tw]::SendMessage($tree, 0x1102, [IntPtr]2, $item); $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]4, $item) }
    }
    [void][Tw]::SendMessage($tree, 0x1102, [IntPtr]2, $item); [void][Tw]::SendMessage($tree, 0x1114, [IntPtr]0, $item); [void][Tw]::SendMessage($tree, 0x110B, [IntPtr]9, $item)
  }
  'reach' {
    # in the Index-th visible tree: expand the Root-th top item only, then show and select its Child-th child
    $w = $tops | Where-Object { [Tw]::Cls($_) -eq 'TfrmFrame' -and [Tw]::IsWindowVisible($_) } | Select-Object -First 1
    $trees = @([Tw]::Kids($w) | Where-Object { [Tw]::Cls($_) -like '*TreeView*' -and [Tw]::IsWindowVisible($_) })
    $n = 0; foreach ($t in $trees) { "tree $n : " + (Describe $t); $n++ }
    $tree = $trees[$Index]; $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]0, [IntPtr]0)
    $roots = @(); while ($item -ne [IntPtr]::Zero) { $roots += $item; $item = [Tw]::SendMessage($tree, 0x110A, [IntPtr]1, $item) }  # TVGN_NEXT
    "roots: " + $roots.Count
    foreach ($r in $roots) { [void][Tw]::SendMessage($tree, 0x1102, [IntPtr]1, $r) }  # collapse all
    [void][Tw]::SendMessage($tree, 0x1102, [IntPtr]2, $roots[$Root])
    $kid = [Tw]::SendMessage($tree, 0x110A, [IntPtr]4, $roots[$Root]); $count = 0; $all = 0  # TVGN_CHILD
    $walk = $kid; while ($walk -ne [IntPtr]::Zero) { $all++; $walk = [Tw]::SendMessage($tree, 0x110A, [IntPtr]1, $walk) }
    while ($count -lt $Child -and $kid -ne [IntPtr]::Zero) { $kid = [Tw]::SendMessage($tree, 0x110A, [IntPtr]1, $kid); $count++ }
    "children: $all; reached child $count"
    if ($kid -ne [IntPtr]::Zero) { [void][Tw]::SendMessage($tree, 0x1114, [IntPtr]0, $kid); [void][Tw]::SendMessage($tree, 0x110B, [IntPtr]9, $kid) }  # TVM_ENSUREVISIBLE, TVM_SELECTITEM caret
  }
}
